#!/usr/bin/env python3
"""
Find callers of functions in the DA14585 mask ROM.

Ghidra's scripting API is awkward to drive headless, but the question we need answered
is purely mechanical: which code calls a given ROM function? The DA14585 ROM is 128 KB of
readable Thumb code and the SDK supplies 794 symbol names, so capstone can walk it and
resolve every `bl` target to a symbol.

Usage:
    ./venv/bin/python rom_callers.py ke_msg_send 0x07F1BBE2
    ./venv/bin/python rom_callers.py --all
"""

import argparse
import struct
import subprocess
import sys
from collections import defaultdict

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS

ROM_BASE = 0x07F00000
ROM_SIZE = 0x20000
ELF = "firmware/build/eink_ble_firmware.elf"
ROM_BIN = "ke_rom_128k.bin"


def load_symbols():
    out = subprocess.run(["arm-none-eabi-nm", "-n", ELF],
                         capture_output=True, text=True, check=True).stdout
    syms = []
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 3:
            v = int(p[0], 16)
            if ROM_BASE <= v < ROM_BASE + ROM_SIZE:
                syms.append((v, p[2]))
    syms.sort()
    return syms


def containing(addr, syms):
    import bisect
    addrs = [s[0] for s in syms]
    i = bisect.bisect_right(addrs, addr) - 1
    if i < 0:
        return None
    base, name = syms[i]
    return (name, addr - base)


def disassemble(rom, syms):
    """Disassemble from each symbol entry point, so functions get sensible boundaries."""
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    md.detail = False
    insns = []
    starts = [s[0] for s in syms]
    seen = set()
    for start in starts:
        if start in seen:
            continue
        seen.add(start)
        for i in md.disasm(rom[start - ROM_BASE:start - ROM_BASE + 0x800], start):
            insns.append((i.address, i.mnemonic, i.op_str, i.size))
            if i.mnemonic in ("bx", "pop") and "pc" in i.op_str:
                break
    return insns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", help="symbol to find callers of")
    ap.add_argument("addr", nargs="?", help="its address, e.g. 0x07F1BBE2")
    ap.add_argument("--all", action="store_true", help="summarise every ROM function's caller count")
    a = ap.parse_args()

    rom = open(ROM_BIN, "rb").read()
    syms = load_symbols()
    print(f"[+] ROM {len(rom)} bytes, {len(syms)} symbols")
    insns = disassemble(rom, syms)
    print(f"[+] disassembled {len(insns)} instructions from {len(syms)} entry points\n")

    # Map: target address -> list of caller sites
    callers = defaultdict(list)
    for addr, mn, ops, size in insns:
        if mn.startswith("bl") or mn == "b":
            try:
                tgt = int(ops.strip().lstrip("#"), 0)
            except ValueError:
                continue
            if ROM_BASE <= tgt < ROM_BASE + ROM_SIZE:
                callers[tgt].append(addr)

    if a.all:
        rows = []
        for base, name in syms:
            rows.append((len(callers.get(base, [])), name, base))
        rows.sort(reverse=True)
        for n, name, base in rows[:40]:
            print(f"  {n:4d} callers  {name} @ 0x{base:08X}")
        return 0

    if not a.name or not a.addr:
        ap.error("need a symbol name and address, or --all")

    target = int(a.addr, 16)
    match = [s for s in syms if s[1] == a.name]
    if match and match[0][0] != target:
        print(f"[!] note: {a.name} is actually at 0x{match[0][0]:08X}")

    sites = callers.get(target, [])
    print(f"callers of {a.name} (0x{target:08X}): {len(sites)}")
    byfn = defaultdict(list)
    for s in sites:
        c = containing(s, syms)
        byfn[c[0] if c else "?"].append(s)
    for fn, ss in sorted(byfn.items(), key=lambda kv: -len(kv[1])):
        print(f"\n  {fn}  ({len(ss)} call site(s))")
        for s in ss[:8]:
            print(f"      0x{s:08X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
