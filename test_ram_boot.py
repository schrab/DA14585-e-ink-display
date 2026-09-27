"""
Test RAM Boot: Load and execute custom firmware directly in SysRAM via SWD
========================================================================
Loads firmware/build/eink_firmware.bin into SysRAM at 0x07FC0000 and boots the Cortex-M0.
"""

import sys
import time
import struct
from pyocd.core.helpers import ConnectHelper
from pyocd.core.exceptions import Error as PyOCDError

SYSRAM_BASE = 0x07FC0000
DEFAULT_BIN = "firmware/build/eink_ble_firmware.bin"
FALLBACK_BIN = "firmware/build/eink_firmware.bin"

def main():
    print("=" * 65)
    print("DA14585 SysRAM Firmware Boot & Verification")
    print("=" * 65)

    import os
    if len(sys.argv) > 1:
        bin_path = sys.argv[1]
    elif os.path.exists(DEFAULT_BIN):
        bin_path = DEFAULT_BIN
    else:
        bin_path = FALLBACK_BIN

    with open(bin_path, "rb") as f:
        bin_data = f.read()

    print(f"[+] Loaded binary: {bin_path} ({len(bin_data)} bytes)")
    sp, pc = struct.unpack("<II", bin_data[:8])
    print(f"    - Initial SP: 0x{sp:08X}")
    print(f"    - Reset PC  : 0x{pc:08X}")

    probes = ConnectHelper.get_all_connected_probes()
    if not probes:
        print("[-] No ST-Link probe detected!")
        sys.exit(1)

    probe = probes[0]
    session = ConnectHelper.session_with_chosen_probe(
        unique_id=probe.unique_id,
        target_override="cortex_m",
        options={
            "frequency": 1000000,
            "connect_mode": "attach",
            "resume_on_disconnect": False,
        }
    )
    session.open()
    target = session.target

    print("[+] Connected to DA14585 over SWD.")
    target.halt()
    print("[+] Core halted.")

    # Freeze watchdog and reload immediately while loading
    target.write16(0x50003100, 0x00C8)
    target.write16(0x50003300, 0x0008)

    # Enable SWD and remap SysRAM1 (0x07FC0000) to 0x0 (REMAP_ADR0 = 2, DEBUGGER_ENABLE = 0x80)
    sys_ctrl = target.read16(0x50000012)
    target.write16(0x50000012, (sys_ctrl & ~0x3) | 0x0082)
    print(f"[+] SYS_CTRL_REG set to 0x{target.read16(0x50000012):04X} (SysRAM1 remapped to 0x0, debugger enabled)")

    # Load binary to SysRAM at 0x07FC0000
    print(f"[*] Uploading {len(bin_data)} bytes to 0x{SYSRAM_BASE:08X}...")
    target.write_memory_block8(SYSRAM_BASE, list(bin_data))
    print("[+] Upload complete! Verifying integrity...")

    readback = bytes(target.read_memory_block8(SYSRAM_BASE, len(bin_data)))
    if readback != bin_data:
        print("[-] Error: Readback mismatch in SysRAM!")
        sys.exit(1)
    print("[+] Memory verified 100% bit-exact!")

    if not target.is_halted():
        target.halt()

    # Set initial SP, PC, LR while halted
    target.write_core_register("sp", sp)
    target.write_core_register("pc", pc)
    target.write_core_register("lr", 0xFFFFFFFF)
    print(f"[+] Set SP = 0x{sp:08X}, PC = 0x{pc:08X}")

    # Pet watchdog right before resuming
    target.write16(0x50003100, 0x00C8)

    print("[+] Resuming core execution...")
    target.resume()

    print("[*] Monitoring execution for 10 seconds...")
    for i in range(10):
        time.sleep(1)
        state = target.get_state()
        p0 = target.read16(0x50003000)
        p2 = target.read16(0x50003040)
        p0_mode = target.read16(0x50003006)
        print(f"    T+{i+1:2d}s | State: {state.name:<8} | P0: 0x{p0:04X} | P2: 0x{p2:04X} | P0_0 Mode: 0x{p0_mode:04X}")

    session.close()
    print("\n[+] Verification run completed.")

if __name__ == "__main__":
    main()
