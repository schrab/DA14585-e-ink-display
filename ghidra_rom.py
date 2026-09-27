"""
Ghidra (PyGhidra) driver for the DA14585 mask ROM.

The whole RivieraWaves BLE stack lives in mask ROM, so the Write-With-Request HardFault
can only be settled by reading it. The ROM is fully readable over SWD; `ke_rom_dump.py`
extracts it plus 794 symbol names from da14585_586.lib, and Ghidra imports it at base
0x07F00000 as ARM Cortex-M0.

This labels the image, then decompiles functions around the fault and reports XREFs.

Usage:
    ./venv/bin/python ghidra_rom.py --decompile 07f1bbe2:ke_msg_send
"""

import argparse
import sys

import pyghidra


def addr(program, v):
    return program.getAddressFactory().getDefaultAddressSpace().getAddress(v)


def apply_symbols(program, csv_path):
    from ghidra.program.model.symbol import SourceType
    st = program.getSymbolTable()
    mem = program.getMemory()
    ok = bad = 0
    with open(csv_path) as f:
        next(f, None)                                  # header
        for line in f:
            line = line.strip()
            if not line:
                continue
            name, _, a = line.rpartition(",")
            try:
                address = addr(program, int(a))
            except ValueError:
                bad += 1
                continue
            if address is None or not mem.contains(address):
                bad += 1
                continue
            st.createLabel(address, name, SourceType.USER_DEFINED)
            ok += 1
    print(f"[+] labelled {ok} symbols ({bad} skipped)")


def ensure_function(program, v, name, body_len=0x400):
    from ghidra.program.model.symbol import SourceType
    from ghidra.program.model.address import AddressSet
    a = addr(program, v)
    fm = program.getFunctionManager()
    f = fm.getFunctionAt(a)
    if f is None:
        body = AddressSet(a, addr(program, v + body_len))
        f = fm.createFunction(name, a, body, SourceType.USER_DEFINED)
    if f is not None and name and f.getName() != name:
        f.setName(name, SourceType.USER_DEFINED)
    return f


def show_xrefs(program, f):
    refs = program.getReferenceManager().getReferencesTo(f.getEntryPoint())
    refs = list(refs) if refs else []
    print(f"  XREFs to it: {len(refs)}")
    fm = program.getFunctionManager()
    for r in refs[:40]:
        fa = fm.getFunctionContaining(r.getFromAddress())
        print(f"     from {r.getFromAddress()}  in "
              f"{fa.getName() if fa else '?'}  ({r.getReferenceType()})")


def decompile(decomp, f):
    res = decomp.decompileFunction(f, 90, pyghidra.task_monitor())
    if res is None:
        return "!! decompile returned None"
    if not res.decompileCompleted():
        return f"!! decompile failed: {res.getErrorMessage()}"
    df = res.getDecompiledFunction()
    return df.getC() if df is not None else "!! no body"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="/tmp/opencode/ghidra_proj")
    ap.add_argument("--project-name", default="da14585")
    ap.add_argument("--program", default="/ke_rom_128k.bin")
    ap.add_argument("--csv", default="ke_rom_symbols.csv")
    ap.add_argument("--apply-symbols", action="store_true")
    ap.add_argument("--decompile", nargs="*", default=[], help="addr:name pairs")
    a = ap.parse_args()

    pyghidra.start()

    def work(program):
        print(f"[+] program {program.getName()}  "
              f"{program.getMinAddress()}-{program.getMaxAddress()}")
        if a.apply_symbols:
            apply_symbols(program, a.csv)

        if not a.decompile:
            return

        from ghidra.app.decompiler import DecompInterface, DecompileOptions
        decomp = DecompInterface()
        decomp.setOptions(DecompileOptions())
        decomp.openProgram(program)

        for spec in a.decompile:
            as_, _, name = spec.partition(":")
            v = int(as_, 16)
            f = ensure_function(program, v, name or f"fn_{as_}")
            if f is None:
                print(f"!! could not create a function at 0x{v:08X}")
                continue
            print("\n" + "=" * 78)
            print(f"  {f.getName()} @ {f.getEntryPoint()}")
            print("=" * 78)
            show_xrefs(program, f)
            print("  --- decompiled ---")
            print(decompile(decomp, f))
        decomp.dispose()

    project = pyghidra.open_project(a.project, a.project_name, create=False)
    pyghidra.consume_program(project, a.program, work)
    return 0


if __name__ == "__main__":
    sys.exit(main())
