#!/usr/bin/env python3
"""
Step-zero experiment: does the ATT Write-Request HardFault reproduce in a
PRODUCTION build (EINK_DIAG=0, MSG_HEAP_SZ=1904)?

MSG_HEAP_SZ is guarded by `#if !EINK_DIAG`, so diagnostic builds silently fall
back to the SDK default 1392 B pool. Every write-with-response crash observed so
far was captured on a diagnostic build, i.e. against the *unfixed* pool. If the
fault does not reproduce with 1904 B, the whole open question was an artefact of
the test configuration.

This script deliberately issues ONE 1-byte write-with-response and never sends
the refresh command, so the e-ink panel is not touched.

Usage:
  ./venv/bin/python stepzero_write_req.py            # write with response
  ./venv/bin/python stepzero_write_req.py --noresp   # control: write cmd
  ./venv/bin/python stepzero_write_req.py --heaps    # just walk the KE heaps
"""
import argparse
import asyncio
import sys

from bleak import BleakClient

CMD_CHAR = "9e1547ba-c365-57b5-2947-c5e1c1e1d528"
NAME_HINT = "EINK"


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


async def find_device():
    from bleak import BleakScanner

    found = await BleakScanner.discover(timeout=10.0, return_adv=True)
    for addr, (_dev, adv) in found.items():
        if "eink" in (adv.local_name or "").lower():
            return addr
    die(f"no device matching EINK found; saw: "
        f"{[(a, adv.local_name) for a, (_d, adv) in found.items()]}")


async def heap_walk():
    """No BT needed; delegate to the existing ROM/heap tool."""
    import subprocess

    subprocess.run([sys.executable, "ke_rom_dump.py", "--heaps"], check=False)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noresp", action="store_true", help="control: write WITHOUT response")
    ap.add_argument("--heaps", action="store_true", help="SWD heap walk only, no BLE")
    ap.add_argument("--cmd", default="0x08", help="command byte to send (default 0x08 status)")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()

    if args.heaps:
        await heap_walk()
        return

    dev = await find_device()
    print(f"connecting to {dev} ...")
    async with BleakClient(dev, timeout=args.timeout) as client:
        print("connected")

        # Commands: 0x08 = status query (safe), 0x07 = clear framebuffer (safe,
        # does not touch the panel). 0x06 = refresh is deliberately NOT offered:
        # this experiment must not drive the e-ink panel.
        if args.cmd == "0x06":
            die("refusing to send 0x06: this experiment must not refresh the panel")
        payload = bytearray([int(args.cmd, 16), 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        if args.noresp:
            print("sending ONE write WITHOUT response (control)")
            await client.write_gatt_char(CMD_CHAR, payload, response=False)
        else:
            print("sending ONE write WITH response")
            await client.write_gatt_char(CMD_CHAR, payload, response=True)
        print("write returned; sleeping 3s to see if the core survives ...")
        await asyncio.sleep(3.0)
        print("still connected (no fault)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("interrupted")
