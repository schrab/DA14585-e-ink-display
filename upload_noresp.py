#!/usr/bin/env python3
"""
Upload a tri-color image using ATT Write Without Response, then trigger the refresh.

Write Without Response is used for every write because the Write-With-Response path
currently hardfaults the firmware inside the ROM's ATT response handler
(ke_queue_insert branches to a garbage handler for an LLC message whose block overlaps
a freed KE message-pool block). Commands therefore go out fire-and-forget, which means
there is no ATT acknowledgement to wait for - we simply allow time for the panel cycle.

Usage:
    ./venv/bin/python upload_noresp.py --image test_pattern_red_400x300.png
"""

import argparse
import asyncio
import sys
import time

from bleak import BleakClient, BleakScanner

sys.path.insert(0, ".")
from ble_eink_client import (  # noqa: E402
    CHAR_CMD_UUID,
    CHAR_IMAGE_UUID,
    MAX_CHUNK_PAYLOAD,
    convert_image_to_tricolor_buffer,
)

CLEAR = bytes([0x07])
REFRESH = bytes([0x06])


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
    ap.add_argument("--settle", type=float, default=1.0,
                    help="seconds between packets")
    args = ap.parse_args()

    data = convert_image_to_tricolor_buffer(args.image)
    addr = args.device or await find_device()
    if not addr:
        print("[-] E-Ink display not found")
        return 1

    total = len(data)
    chunks = (total + MAX_CHUNK_PAYLOAD - 1) // MAX_CHUNK_PAYLOAD
    print(f"[+] {args.image} -> {total} byte dual-plane buffer, {chunks} packets")
    print(f"[+] Connecting to {addr} (Write Without Response)...")

    async with BleakClient(addr) as client:
        await client.write_gatt_char(CHAR_CMD_UUID, CLEAR, response=False)
        print("[+] Buffer cleared")

        t0 = time.time()
        for i in range(chunks):
            off = i * MAX_CHUNK_PAYLOAD
            pkt = bytearray([off & 0xFF, (off >> 8) & 0xFF])
            pkt += data[off : off + MAX_CHUNK_PAYLOAD]
            await client.write_gatt_char(CHAR_IMAGE_UUID, pkt, response=False)
            await asyncio.sleep(args.settle)
            if (i + 1) % 25 == 0 or i + 1 == chunks:
                pct = (i + 1) / chunks * 100
                print(f"    {i+1}/{chunks} ({pct:.0f}%)", flush=True)
        dt = time.time() - t0
        print(f"[+] Streamed {total} bytes in {dt:.1f}s ({total/dt/1024:.1f} KB/s)")

        print("[*] Triggering e-ink refresh (0x06)...")
        await client.write_gatt_char(CHAR_CMD_UUID, REFRESH, response=False)
        print("[+] Refresh command sent; panel will cycle for ~17s")
        await asyncio.sleep(2.0)
        print("[*] Closing the link while the panel refreshes...")
        await client.disconnect()

    print("[*] Waiting for the electrophoretic cycle to complete...")
    for i in range(20):
        await asyncio.sleep(1)
        print(f"    {i+1:2d}s", flush=True)
    print("[+] Done. The panel is bistable, so it now holds the new image with zero power.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
