#!/usr/bin/env python3
"""
Read the DA14585 firmware's retained RAM-CRC snapshot history over SWD and diff it.

The firmware CRCs eight RAM regions at each interesting point in the application flow
(see firmware/ble/user_eink_diag.c). A region whose CRC changes between two phases was
written by something other than its owner — that is how we catch the transient
corruption that hardfaults the ROM's ke_queue_insert during a mid-refresh disconnect.

Usage:
    ./venv/bin/python diag_crc.py            # read + diff
    ./venv/bin/python diag_crc.py --verify   # only check the region table vs the map
"""

import argparse
import re
import struct
import subprocess
import sys

ELF = "firmware/build/eink_ble_firmware.elf"
MAP = "firmware/build/eink_ble_firmware.map"

REGION_COUNT = 9
SNAPSHOT_COUNT = 12
SNAPSHOT_STRIDE = 4 + REGION_COUNT * 4  # valid, phase, pad, count, crc[]

PHASES = {
    0: "BOOT",
    1: "CMD_CLEAR",
    2: "PRE_REFRESH",
    3: "POST_REFRESH",
    4: "DISCONNECT",
    5: "CMD_REFRESH",
    6: "CMD_STATUS",
    7: "MANUAL",
    8: "PRE_WRITE",
    9: "POST_WRITE",
}

# Regions whose contents are *expected* to differ between snapshots, because the
# application legitimately writes them. Anything else changing is the interesting bit.
EXPECTED_TO_CHANGE = {"data_bss"}


def elf_sym(name):
    out = subprocess.run(
        ["arm-none-eabi-nm", "-n", ELF], capture_output=True, text=True, check=True
    ).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == name:
            return int(parts[0], 16)
    return None


def map_symbols():
    """Pull the linker-provided boundary symbols out of the map."""
    try:
        text = open(MAP).read()
    except OSError:
        return {}

    wanted = (
        "__data_start__",
        "__heap_mem_area_not_ret_start__",
        "__heap_mem_area_not_ret_end__",
        "__HeapLimit",
        "__StackLimit",
        "__StackTop",
        "__db_heap_start__",
        "__db_heap_end__",
    )
    found = {}
    for sym in wanted:
        m = re.search(rf"0x([0-9a-f]+)\s+{re.escape(sym)}\s*=", text)
        if m:
            found[sym] = int(m.group(1), 16)

    # These are emitted as bare "ADDR  rwip_heap_*" placement lines.
    for sym in ("rwip_heap_db_ret", "rwip_heap_msg_ret"):
        m = re.search(rf"0x([0-9a-f]+)\s+{sym}\b", text)
        if m:
            found[sym] = int(m.group(1), 16)
    return found


def map_section_size(section):
    """Return (addr, size) for a top-level output section in the linker map."""
    try:
        text = open(MAP).read()
    except OSError:
        return None
    m = re.search(rf"^{re.escape(section)}\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)", text, re.M)
    if not m:
        return None
    return int(m.group(1), 16), int(m.group(2), 16)


def verify_regions(regions):
    """Cross-check the firmware's hardcoded region table against the current link map."""
    problems = []

    diag_addr = elf_sym("diag_history")
    diag_next = elf_sym("diag_next")
    if diag_addr is None:
        return ["diag_history not found in ELF - rebuild first"]

    diag_lo = min(diag_addr, diag_next)
    diag_hi = diag_addr + SNAPSHOT_COUNT * (4 + REGION_COUNT * 4)  # generous upper bound

    s = map_symbols()
    if not s:
        return ["could not parse the linker map"]

    for name, addr, size in regions:
        end = addr + size
        if diag_lo < end and addr < diag_hi:
            problems.append(
                f"{name} (0x{addr:08X}+0x{size:X}) overlaps diag history "
                f"(0x{diag_lo:08X}..0x{diag_hi:08X}) - snapshots would perturb themselves"
            )

    # Each region must start exactly where the previous one ends: the table is a
    # hand-maintained partition of RAM, so any gap or overlap means it has drifted.
    order = [
        ("code", 0x07FC0000),
        ("data_bss", s.get("__data_start__")),
        ("rwip_nonret", s.get("__heap_mem_area_not_ret_start__")),
        ("gaptail", s.get("__HeapLimit")),
        ("retention", elf_sym("intr_cb")),
        ("heap_env", s.get("__db_heap_start__")),
        ("heap_db", s.get("rwip_heap_db_ret")),
        ("heap_msg", s.get("rwip_heap_msg_ret")),
        ("rom_tables", s.get("__db_heap_end__")),
    ]
    for name, want_lo in order:
        got = next((r for r in regions if r[0] == name), None)
        if got is None:
            problems.append(f"{name} missing from the table")
            continue
        if want_lo is not None and got[1] != want_lo:
            problems.append(
                f"{name} starts at 0x{got[1]:08X} but the map says 0x{want_lo:08X}"
            )

    # Terminal boundaries.
    ends = {
        "rwip_nonret": s.get("__heap_mem_area_not_ret_end__"),
        "gaptail": s.get("__StackTop"),
        "heap_env": s.get("rwip_heap_db_ret"),
        "heap_db": s.get("rwip_heap_msg_ret"),
        "heap_msg": s.get("__db_heap_end__"),
    }
    for name, want_end in ends.items():
        got = next((r for r in regions if r[0] == name), None)
        if got and want_end is not None and got[1] + got[2] != want_end:
            problems.append(
                f"{name} ends at 0x{got[1] + got[2]:08X} but the map says 0x{want_end:08X}"
            )

    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="only validate the region table")
    args = ap.parse_args()

    # Region table as compiled into the firmware, mirrored here for verification.
    regions = [
        ("code", 0x07FC0000, 0x78E0),
        ("data_bss", 0x07FC78E0, 0x766C),
        ("rwip_nonret", 0x07FCEF4C, 0x040C),
        ("gaptail", 0x07FCF358, 0x08A8),
        ("retention", 0x07FD4B80, 0x044C),
        ("heap_env", 0x07FD4FCC, 0x0274),
        ("heap_db", 0x07FD5240, 0x040C),
        ("heap_msg", 0x07FD564C, 0x057C),
        ("rom_tables", 0x07FD5BC8, 0x2438),
    ]

    problems = verify_regions(regions)
    if problems:
        print("[!] Region table is STALE for the current link map:")
        for p in problems:
            print("    - " + p)
        print("    Re-derive the table in firmware/ble/user_eink_diag.c from the map.")
    else:
        print("[+] Region table matches the current linker map.")
    if args.verify:
        return 1 if problems else 0

    from pyocd.core.helpers import ConnectHelper

    probe = ConnectHelper.get_all_connected_probes()[0]
    session = ConnectHelper.session_with_chosen_probe(
        unique_id=probe.unique_id, target_override="cortex_m", connect_mode="attach"
    )
    session.open()
    target = session.target
    if target.get_state().name != "HALTED":
        target.halt()

    base = elf_sym("diag_history")
    total = target.read8(elf_sym("diag_next"))
    print(f"[+] diag_history @ 0x{base:08X}, {total} snapshot(s) recorded")

    snaps = []
    for i in range(min(total, SNAPSHOT_COUNT)):
        raw = bytes(target.read_memory_block8(base + i * SNAPSHOT_STRIDE, SNAPSHOT_STRIDE))
        valid, phase, _pad, count = struct.unpack_from("<BBBH", raw)
        crcs = struct.unpack_from("<%dI" % REGION_COUNT, raw, 4)
        snaps.append((valid, phase, count, crcs))

    session.close()

    if not snaps:
        print("[!] No snapshots recorded yet.")
        return 0

    print()
    hdr = "phase".ljust(14) + "".join(n[:11].rjust(12) for n, _, _ in regions)
    print(hdr)
    print("-" * len(hdr))
    for valid, phase, count, crcs in snaps:
        name = PHASES.get(phase, f"?{phase}")
        row = f"{name}({count})".ljust(14)
        for v in crcs:
            row += f"{v:08X}".rjust(12)
        print(row)

    print()
    print("Deltas vs previous phase:")
    for i in range(1, len(snaps)):
        prev, cur = snaps[i - 1], snaps[i]
        changed = [
            regions[j][0]
            for j in range(REGION_COUNT)
            if prev[3][j] != cur[3][j]
        ]
        if not changed:
            print(f"  {PHASES.get(prev[1],'?'):<12} -> {PHASES.get(cur[1],'?'):<12} (no change)")
            continue
        for name in changed:
            tag = "(expected)" if name in EXPECTED_TO_CHANGE else "*** UNEXPECTED ***"
            j = [r[0] for r in regions].index(name)
            print(
                f"  {PHASES.get(prev[1],'?'):<12} -> {PHASES.get(cur[1],'?'):<12} "
                f"{name:<12} {prev[3][j]:08X} -> {cur[3][j]:08X}  {tag}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
