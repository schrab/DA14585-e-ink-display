#!/usr/bin/env python3
"""
Regenerate the diag region table in firmware/ble/user_eink_diag.c from the linker map.

The monitored regions are a hand-partitioned view of RAM, so adding or removing code
shifts every boundary. Run this after any build that changes .bss or retained-RAM usage,
then `diag_crc.py --verify` will confirm the result.

    ./venv/bin/python regen_diag_regions.py
"""

import pathlib
import re
import subprocess
import sys

MAP = "firmware/build/eink_ble_firmware.map"
ELF = "firmware/build/eink_ble_firmware.elf"
CFILE = pathlib.Path("firmware/ble/user_eink_diag.c")
PYFILE = pathlib.Path("diag_crc.py")

# region name -> (start source, end source)
#   "const"   a fixed address
#   "sym"     a linker-provided boundary symbol
#   "elf"     an ELF symbol name
SYSRAM4_END = 0x07FD8000


def map_symbols():
    text = open(MAP).read()
    wanted = (
        "__data_start__",
        "__heap_mem_area_not_ret_start__",
        "__heap_mem_area_not_ret_end__",
        "__HeapLimit",
        "__StackTop",
        "__db_heap_start__",
        "__db_heap_end__",
    )
    out = {}
    for sym in wanted:
        m = re.search(rf"0x([0-9a-f]+)\s+{re.escape(sym)}\s*=", text)
        if m:
            out[sym] = int(m.group(1), 16)
    for sym in ("rwip_heap_db_ret", "rwip_heap_msg_ret"):
        m = re.search(rf"0x([0-9a-f]+)\s+{sym}\b", text)
        if m:
            out[sym] = int(m.group(1), 16)
    if not out:
        sys.exit("could not parse the linker map - build first")
    return out


def elf_sym(name):
    out = subprocess.run(
        ["arm-none-eabi-nm", "-n", ELF], capture_output=True, text=True, check=True
    ).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == name:
            return int(parts[0], 16)
    sys.exit(f"symbol {name} not found in the ELF")


def main():
    s = map_symbols()
    intr_cb = elf_sym("intr_cb")

    bounds = [
        ("code",        0x07FC0000,                       s["__data_start__"]),
        ("data_bss",    s["__data_start__"],               s["__heap_mem_area_not_ret_start__"]),
        ("rwip_nonret", s["__heap_mem_area_not_ret_start__"], s["__heap_mem_area_not_ret_end__"]),
        ("gaptail",     s["__HeapLimit"],                  s["__StackTop"]),
        ("retention",   intr_cb,                           s["__db_heap_start__"]),
        ("heap_env",    s["__db_heap_start__"],            s["rwip_heap_db_ret"]),
        ("heap_db",     s["rwip_heap_db_ret"],             s["rwip_heap_msg_ret"]),
        ("heap_msg",    s["rwip_heap_msg_ret"],            s["__db_heap_end__"]),
        ("rom_tables",  s["__db_heap_end__"],              SYSRAM4_END),
    ]

    for i, (name, lo, hi) in enumerate(bounds):
        if hi <= lo:
            sys.exit(f"region {name} is inverted: 0x{lo:08X}..0x{hi:08X}")
        if i and lo != bounds[i - 1][2]:
            print(f"[!] note: gap/overlap before {name}: "
                  f"prev ends 0x{bounds[i-1][2]:08X}, {name} starts 0x{lo:08X}")

    c_rows = "\n".join(
        f'    {{ "{n}",{"" if len(n) >= 11 else " "*(11-len(n))} 0x{lo:08X}u, 0x{hi-lo:04X}u }},'
        for n, lo, hi in bounds
    )
    t = CFILE.read_text()
    i = t.index('    { "code"')
    j = t.index("};", i)
    CFILE.write_text(t[:i] + c_rows + "\n" + t[j:])

    py_rows = "\n".join(
        f'        ("{n}", 0x{lo:08X}, 0x{hi-lo:04X}),' for n, lo, hi in bounds
    )
    p = PYFILE.read_text()
    a = p.index('        ("code", 0x07FC0000,')
    b = p.index("    ]", a)
    PYFILE.write_text(p[:a] + py_rows + "\n" + p[b:])

    print("[+] Region table regenerated:")
    for n, lo, hi in bounds:
        print(f"    {n:<12} 0x{lo:08X} .. 0x{hi:08X}  (0x{hi-lo:04X})")


if __name__ == "__main__":
    main()
