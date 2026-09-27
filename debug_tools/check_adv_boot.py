"""
DA14585 SWD RAM Boot & Breakpoint Diagnostic
============================================
Loads binary into SysRAM at 0x07FC0000, sets breakpoints on key SDK stages
(DB init, advertising start, HardFault), and monitors core state.
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

    # Set initial registers
    target.write_core_register("sp", sp_init)
    target.write_core_register("pc", pc_init)

    # Breakpoint addresses from ELF symbol table
    target.set_breakpoint(0x07FC49EC) # default_app_on_db_init_complete
    target.set_breakpoint(0x07FC0734) # user_app_adv_start
    target.set_breakpoint(0x07FC1CF8) # HardFault_HandlerC

    # Pet watchdog and resume
    target.write16(0x50003100, 0x00C8)
    target.resume()

    print("[*] Waiting for target to hit breakpoint...")
    for i in range(40):
        time.sleep(0.2)
        state = target.get_state().name
        if state == "HALTED":
            pc = target.read_core_register("pc")
            lr = target.read_core_register("lr")
            sp = target.read_core_register("sp")
            print(f"[+] Halted! PC=0x{pc:08X} | LR=0x{lr:08X} | SP=0x{sp:08X}")
            break

    session.close()

if __name__ == "__main__":
    main()
