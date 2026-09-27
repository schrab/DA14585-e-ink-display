#!/usr/bin/env python3
"""
Deterministic reproducer for the DA14585 mid-refresh HardFault.

Connects over BLE, streams a tri-color image, triggers the e-ink refresh, then drops
the link while the firmware is still blocked inside the ~17 s refresh. That is exactly
what happens when a user clicks "Disconnect" in a Bluetooth applet mid-upload, and it
is the trigger for the ROM's ke_queue_insert branching into a garbage handler.

Afterwards, read the retained CRC history with diag_crc.py to see which RAM region was
written by something that should not have touched it.

Usage:
    ./venv/bin/python repro_disconnect.py --image test_pattern_red_400x300.png
"""

import argparse
import asyncio
import sys

from bleak import BleakClient, BleakScanner

sys.path.insert(0, ".")
from ble_eink_client import (  # noqa: E402
    CHAR_CMD_UUID,
    CHAR_IMAGE_UUID,
    MAX_CHUNK_PAYLOAD,
    convert_image_to_tricolor_buffer,
)

REFRESH_CMD = bytes([0x06])
CLEAR_CMD = bytes([0x07])


async def find_device():
    found = await BleakScanner.discover(timeout=10.0, return_adv=True)
    for addr, (_dev, adv) in found.items():
        if "eink" in (adv.local_name or "").lower():
            return addr
    return None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", "-i", default="test_pattern_red_400x300.png")
    ap.add_argument("--device", "-d", default=None)
    ap.add_argument(
        "--drop-after",
        type=float,
        default=0.4,
        help="seconds to wait after the refresh command before dropping the link",
    )
    args = ap.parse_args()

    data = convert_image_to_tricolor_buffer(args.image)
    addr = args.device or await find_device()
    if not addr:
        print("[-] E-Ink display not found")
        return 1

    print(f"[+] Connecting to {addr}...")
    async with BleakClient(addr) as client:
        await client.write_gatt_char(CHAR_CMD_UUID, CLEAR_CMD, response=True)
        print("[+] Buffer cleared")

        total = len(data)
        chunks = (total + MAX_CHUNK_PAYLOAD - 1) // MAX_CHUNK_PAYLOAD
        for i in range(chunks):
            off = i * MAX_CHUNK_PAYLOAD
            pkt = bytearray([off & 0xFF, (off >> 8) & 0xFF])
            pkt += data[off : off + MAX_CHUNK_PAYLOAD]
            await client.write_gatt_char(CHAR_IMAGE_UUID, pkt, response=False)
            await asyncio.sleep(0.01)
        print(f"[+] Streamed {total} bytes in {chunks} packets")

        print("[*] Sending refresh command (0x06)...")
        try:
            await client.write_gatt_char(CHAR_CMD_UUID, REFRESH_CMD, response=True)
            print("[+] Refresh acknowledged")
        except Exception as exc:
            print(f"[*] Refresh write failed: {exc}")

        # The firmware now blocks for ~17 s inside epd_display_refresh_tricolor().
        # Dropping the link here is the trigger under investigation.
        print(f"[*] Waiting {args.drop_after}s, then dropping the link MID-REFRESH...")
        await asyncio.sleep(args.drop_after)
        await client.disconnect()
        print("[+] Link dropped mid-refresh")

    print("[*] Waiting for the panel cycle to finish (~20s)...")
    await asyncio.sleep(20)
    print("[*] Now run:  ./venv/bin/python diag_crc.py")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
