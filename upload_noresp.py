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
import struct
import sys
import time

from bleak import BleakClient, BleakScanner

sys.path.insert(0, ".")

from dither_convert import convert as dither_convert  # noqa: E402
from ble_eink_client import (  # noqa: E402
    CHAR_CMD_UUID,
    CHAR_IMAGE_UUID,
    MAX_CHUNK_PAYLOAD,
    convert_image_to_tricolor_buffer,
)

CLEAR = bytes([0x07])
REFRESH = bytes([0x06])
STATUS = bytes([0x08])

CHUNK = 240                 # must match EINK_CHUNK_SIZE in the firmware
NCHUNK = 125                # 30000 / 240
MAP_BYTES = 16              # (125 + 7) // 8


async def find_device():
    found = await BleakScanner.discover(timeout=10.0, return_adv=True)
    for addr, (_dev, adv) in found.items():
        if "eink" in (adv.local_name or "").lower():
            return addr
    return None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", "-i", default="gfx/progromirovay.png")
    ap.add_argument("--device", "-d", default=None)
    ap.add_argument("--settle", type=float, default=0.005,
                    help="seconds between packets")
    ap.add_argument("--rounds", type=int, default=8,
                    help="max verify-and-resend passes")
    ap.add_argument("--refresh", action="store_true",
                    help="send command 0x06 to redraw the panel (slow: ~17 s)")
    ap.add_argument("--dither", default="bayer", choices=["bayer", "fs", "none", "threshold"],
                    help="halftone method: bayer (default), fs (error diffusion), "
                         "none (nearest palette colour) or threshold (legacy hard cut)")
    args = ap.parse_args()

    if args.dither == "threshold":
        data = convert_image_to_tricolor_buffer(args.image)
    else:
        data, _ = dither_convert(args.image, method=args.dither)
    addr = args.device or await find_device()
    if not addr:
        print("[-] E-Ink display not found")
        return 1

    total = len(data)
    chunks = (total + MAX_CHUNK_PAYLOAD - 1) // MAX_CHUNK_PAYLOAD
    print(f"[+] {args.image} -> {total} byte dual-plane buffer, {chunks} packets")
    print(f"[+] Connecting to {addr} (Write Without Response)...")

    async def send_chunk(client, i):
        off = i * CHUNK
        pkt = bytearray([off & 0xFF, (off >> 8) & 0xFF])
        pkt += data[off : off + CHUNK]
        await client.write_gatt_char(CHAR_IMAGE_UUID, pkt, response=False)
        if args.settle:
            await asyncio.sleep(args.settle)

    async def missing_chunks(client):
        """Ask the firmware which chunks it has not received (command 0x08)."""
        done = asyncio.Event()
        got = {}

        def on_notify(_, payload):
            if payload and len(payload) >= MAP_BYTES:
                got["map"] = bytes(payload[:MAP_BYTES])
                done.set()

        await client.start_notify(CHAR_CMD_UUID, on_notify)
        await client.write_gatt_char(CHAR_CMD_UUID, STATUS, response=False)
        try:
            await asyncio.wait_for(done.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            return None
        finally:
            try:
                await client.stop_notify(CHAR_CMD_UUID)
            except Exception:
                pass
        if "map" not in got:
            return None
        m = got["map"]
        return [i for i in range(NCHUNK) if not (m[i >> 3] >> (i & 7)) & 1]

    async with BleakClient(addr) as client:
        await client.write_gatt_char(CHAR_CMD_UUID, CLEAR, response=False)
        print("[+] Buffer cleared")

        t0 = time.time()
        for rnd in range(1, args.rounds + 1):
            if rnd == 1:
                todo = list(range(NCHUNK))
            else:
                await asyncio.sleep(1.0)   # let the stack drain what it already has
                todo = await missing_chunks(client)
                if todo is None:
                    print("[!] Status query timed out; cannot verify this pass")
                    break
                if not todo:
                    print(f"[+] All {NCHUNK} chunks confirmed received after {rnd-1} send pass(es)")
                    break
                print(f"[*] Firmware is missing {len(todo)} chunk(s); re-sending them")

            for n, i in enumerate(todo):
                await send_chunk(client, i)
                if (n + 1) % 25 == 0:
                    print(f"    pass {rnd}: {n+1}/{len(todo)}", flush=True)
        else:
            print("[!] Ran out of resend passes; image may be incomplete")

        dt = time.time() - t0
        print(f"[+] Stream complete in {dt:.1f}s")

        if args.refresh:
            print("[*] Triggering e-ink refresh (0x06)...")
            await client.write_gatt_char(CHAR_CMD_UUID, REFRESH, response=False)
            print("[+] Refresh sent; the panel will cycle for ~17s")
            await client.disconnect()
            for i in range(20):
                await asyncio.sleep(1)
        else:
            print("[*] Disconnecting (--refresh not given, so the panel is untouched)")
            await client.disconnect()

    print("[+] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
