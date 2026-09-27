"""
DA14585 SWD Breakpoint & Return Address Inspector
=================================================
Loads binary into SysRAM, sets breakpoints at critical function entry/exit points,
and dumps CPU registers (PC, LR, SP, R0) upon each halt.
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

    target.write16(0x50003100, 0x00C8)
    target.write16(0x50003300, 0x0008)

    sys_ctrl = target.read16(0x50000012)
    target.write16(0x50000012, (sys_ctrl & ~0x3) | 0x0082)

    target.write_memory_block8(SYSRAM_BASE, list(bin_data))

    target.write_core_register("sp", sp_init)
    target.write_core_register("pc", pc_init)

    target.set_breakpoint(0x07FC1CF8) # HardFault

    target.write16(0x50003100, 0x00C8)
    target.resume()

    for _ in range(50):
        time.sleep(0.05)
        if target.get_state().name == "HALTED":
            break

    pc = target.read_core_register("pc")
    lr = target.read_core_register("lr")
    sp = target.read_core_register("sp")
    r0 = target.read_core_register("r0")
    print(f"Halted at: PC=0x{pc:08X} | LR=0x{lr:08X} | SP=0x{sp:08X} | R0=0x{r0:08X}")

    session.close()

if __name__ == "__main__":
    main()
