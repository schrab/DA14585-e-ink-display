#!/usr/bin/env python3
"""
Dump the DA14585 mask ROM and decode the KE free lists.

The ROM is readable over SWD, so the whole 128 KB can be pulled out for static analysis
(the Dialog stack lives there). This also decodes ke_env and walks every KE heap free
list, which is how the free-block header layout was established.

Usage:
    ./venv/bin/python ke_rom_dump.py --rom      # dump ROM to ke_rom_128k.bin
    ./venv bin/python ke_rom_dump.py --heaps   # decode ke_env + walk free lists
"""

import argparse
import struct
import subprocess
import sys

ROM_BASE = 0x07F00000
ROM_SIZE = 0x20000

KE_ENV = 0x07FD7E78          # absolute symbol: ke_env
KE_MEM_BLOCK_MAX = 4         # derived empirically
KE_HEAP_ARRAY_OFF = 0x3C     # offset of heap[] within ke_env_tag
KE_HEAP_SIZE_OFF = 0x4C      # offset of heap_size[] (uint16 each)
KE_HEAP_USED_OFF = 0x54      # offset of heap_used[] (uint16 each)

MBLOCK_MAGIC = 0xA55A        # free-block marker, seen in every block header

# Each retained heap block is an 8-byte mblock header (magic, size, next) padded to
# 12 bytes in the section, so the block spans payload + 12. The free-list bounds are
# derived from ke_env's heap[] pointers and heap_size[] at run time, NOT hardcoded:
# they shift between builds because MSG_HEAP_SZ is #if !EINK_DIAG, and hardcoded
# bounds silently walk the wrong memory on a differently-configured build.
HEAP_NAMES = ["env", "db", "msg", "nonret"]
MBLOCK_OVERHEAD = 12


def connect():
    from pyocd.core.helpers import ConnectHelper
    probe = ConnectHelper.get_all_connected_probes()[0]
    session = ConnectHelper.session_with_chosen_probe(
        unique_id=probe.unique_id, target_override="cortex_m", connect_mode="attach"
    )
    session.open()
    target = session.target
    if target.get_state().name != "HALTED":
        target.halt()
    return session, target


def dump_rom(target, path):
    buf = bytearray()
    for base in range(ROM_BASE, ROM_BASE + ROM_SIZE, 0x1000):
        buf += bytes(target.read_memory_block8(base, 0x1000))
    open(path, "wb").write(bytes(buf))
    real = sum(1 for x in buf if x != 0xFF)
    print(f"[+] wrote {len(buf)} bytes to {path} ({100.0*real/len(buf):.1f}% non-0xFF)")

    # Report how many ROM symbols we could apply to the dump.
    out = subprocess.run(
        ["arm-none-eabi-nm", "-n", "firmware/build/eink_ble_firmware.elf"],
        capture_output=True, text=True,
    ).stdout
    rom_syms = [
        l.split() for l in out.splitlines()
        if len(l.split()) >= 3
        and ROM_BASE <= int(l.split()[0], 16) < ROM_BASE + ROM_SIZE
    ]
    print(f"[+] {len(rom_syms)} ROM symbols available in the ELF to label the dump")
    csv = "ke_rom_symbols.csv"
    with open(csv, "w") as f:
        f.write("Name,Address\n")
        for p in rom_syms:
            f.write(f"{p[2]},{int(p[0],16)}\n")
    print(f"[+] wrote {csv} (Ghidra: File > Script Manager > ImportSymbolsScript.py)")


def decode_heaps(target):
    print(f"ke_env @ 0x{KE_ENV:08X}")
    raw = bytes(target.read_memory_block8(KE_ENV, 0x60))
    words = struct.unpack_from("<24I", raw, 0)
    print("  queue_sent.next  = 0x%08X" % words[0])
    print("  queue_saved.next = 0x%08X" % words[1])
    print("  queue_timer.next = 0x%08X" % words[2])

    regions = []
    for i in range(KE_MEM_BLOCK_MAX):
        ptr = words[KE_HEAP_ARRAY_OFF // 4 + i]
        size = struct.unpack_from("<H", raw, KE_HEAP_SIZE_OFF + 2 * i)[0]
        used = struct.unpack_from("<H", raw, KE_HEAP_USED_OFF + 2 * i)[0]
        name = HEAP_NAMES[i] if i < len(HEAP_NAMES) else f"heap{i}"
        regions.append((name, ptr, ptr + size + MBLOCK_OVERHEAD))
        print(f"  heap[{i}] = 0x{ptr:08X}  ({name:<6}) payload={size:5d}  free={size-used:5d}")
    print()

    for name, lo, hi in regions:
        print(f"{name} free list, 0x{lo:08X}..0x{hi:08X} ({hi-lo} B):")
        node, broken, n = lo, False, 0
        while n < 64:
            if not (lo <= node < hi):
                print(f"   [{n:2d}] node=0x{node:08X} OUT OF BOUNDS")
                broken = True
                break
            magic, size, nxt = struct.unpack("<HHI", bytes(target.read_memory_block8(node, 8)))
            flag = ""
            if magic != MBLOCK_MAGIC:
                flag += "  <== BAD MAGIC"
                broken = True
            if nxt and not (lo <= nxt < hi):
                flag += "  <== next OUT OF BOUNDS"
                broken = True
            if nxt and nxt <= node:
                flag += "  <== next not advancing"
                broken = True
            print(f"   [{n:2d}] @0x{node:08X} magic=0x{magic:04X} size={size:4d} "
                  f"next=0x{nxt:08X}{flag}")
            if not nxt or broken:
                break
            node, n = nxt, n + 1
        print(f"   -> {'BROKEN' if broken else 'consistent'}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", action="store_true", help="dump the 128 KB mask ROM")
    ap.add_argument("--heaps", action="store_true", help="decode ke_env and walk free lists")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if not (a.rom or a.heaps or a.all):
        a.all = True

    session, target = connect()
    try:
        if a.rom or a.all:
            dump_rom(target, "ke_rom_128k.bin")
        if a.heaps or a.all:
            decode_heaps(target)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
