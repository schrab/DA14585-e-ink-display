"""
DA14585 SWD Single-Step Instruction Tracer
==========================================
Connects via SWD, halts the Cortex-M0, and executes single-step instructions
via target.step(), printing registers (PC, LR, SP, R0) at every step.
"""

import sys
import time
import struct
from pyocd.core.helpers import ConnectHelper

SYSRAM_BASE = 0x07FC0000
BIN_PATH = "firmware/build/eink_ble_firmware.bin"

def main():
    with open(BIN_PATH, "rb") as f:
        bin_data = f.read()

    sp_init, pc_init = struct.unpack("<II", bin_data[:8])

    session = ConnectHelper.session_with_chosen_probe(target_override="cortex_m", connect_mode="attach")
    session.open()
    target = session.target
    target.halt()

    # Freeze watchdog
    target.write16(0x50003100, 0x00C8)
    target.write16(0x50003300, 0x0008)

    # Enable debugger and map SysRAM1 to 0x0
    sys_ctrl = target.read16(0x50000012)
    target.write16(0x50000012, (sys_ctrl & ~0x3) | 0x0082)

    # Load binary to SysRAM
    target.write_memory_block8(SYSRAM_BASE, list(bin_data))

    target.write_core_register("sp", sp_init)
    target.write_core_register("pc", pc_init)

    print("[*] Starting single-step execution...")
    for i in range(100):
        target.step()
        cur_pc = target.read_core_register("pc")
        cur_lr = target.read_core_register("lr")
        cur_sp = target.read_core_register("sp")
        cur_r0 = target.read_core_register("r0")
        print(f"Step {i:03d}: PC=0x{cur_pc:08X} | LR=0x{cur_lr:08X} | SP=0x{cur_sp:08X} | R0=0x{cur_r0:08X}")
        if cur_pc == 0x07FC1CF8 or cur_pc == 0x00000000 or cur_pc > 0xFFFFFFF0:
            print(f"[-] Halt/Fault detected at step {i}!")
            break

    session.close()

if __name__ == "__main__":
    main()
