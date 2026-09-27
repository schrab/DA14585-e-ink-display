"""
DA14585 JEDEC ID Reader Test
============================
Tests reading the external SPI NOR flash JEDEC ID via SWD execution
using the vendor spi_flash_read_jedec_id routine at 0x07FC97C4.
"""

import sys
import time
from pyocd.core.helpers import ConnectHelper
from pyocd.core.exceptions import ProbeError

SET_FREEZE_REG = 0x50003300
WATCHDOG_REG   = 0x50003102

SPI_INIT_ADDR       = 0x07FCA288  # spi_flash_enable / pinmux
SPI_READ_JEDEC_ADDR = 0x07FC97C4  # spi_flash_read_jedec_id(uint32_t *id)

SCRATCH_CODE_ADDR   = 0x07FD0000  # SysRAM4
SCRATCH_DATA_ADDR   = 0x07FD0100
STACK_TOP           = 0x07FD7FE0

def main():
    print("[*] Connecting to DA14585 over SWD...")
    session = ConnectHelper.session_with_chosen_probe(
        target_override="cortex_m",
        options={"frequency": 1000000, "connect_mode": "attach", "resume_on_disconnect": False},
        auto_open=False,
    )
    try:
        session.open()
        target = session.target
        target.halt()
        print("[+] Core halted.")

        # 1. Freeze Watchdog
        target.write16(SET_FREEZE_REG, target.read16(SET_FREEZE_REG) | 0x08)
        target.write16(WATCHDOG_REG, 0x00FF)
        print("[+] Watchdog frozen.")

        # 2. Setup breakpoint hook at SCRATCH_CODE_ADDR:
        # Instruction: bkpt #0 (0xBE00)
        target.write16(SCRATCH_CODE_ADDR, 0xBE00)

        # 3. Call SPI Init: spi_flash_enable()
        print("[*] Calling spi_flash_enable (0x07FCA288)...")
        target.write_core_register("sp", STACK_TOP)
        target.write_core_register("lr", SCRATCH_CODE_ADDR | 1)
        target.write_core_register("pc", SPI_INIT_ADDR | 1)
        target.write_core_register("xpsr", 0x01000000)
        target.resume()

        # Wait for halt
        start = time.time()
        while not target.is_halted():
            if time.time() - start > 1.0:
                target.halt()
                print("[!] Timeout waiting for SPI init, halted manually.")
                break
            time.sleep(0.01)

        print("[+] SPI init completed.")

        # 4. Call JEDEC ID read: spi_flash_read_jedec_id(&result)
        print("[*] Calling spi_flash_read_jedec_id (0x07FC97C4)...")
        target.write32(SCRATCH_DATA_ADDR, 0x00000000)
        target.write_core_register("r0", SCRATCH_DATA_ADDR)
        target.write_core_register("sp", STACK_TOP)
        target.write_core_register("lr", SCRATCH_CODE_ADDR | 1)
        target.write_core_register("pc", SPI_READ_JEDEC_ADDR | 1)
        target.write_core_register("xpsr", 0x01000000)
        target.resume()

        start = time.time()
        while not target.is_halted():
            if time.time() - start > 1.0:
                target.halt()
                print("[!] Timeout waiting for JEDEC read, halted manually.")
                break
            time.sleep(0.01)

        raw_id = target.read32(SCRATCH_DATA_ADDR)
        print(f"[+] Raw JEDEC ID read: 0x{raw_id:08X}")

        mfg_id   = (raw_id >> 16) & 0xFF
        mem_type = (raw_id >> 8) & 0xFF
        capacity = raw_id & 0xFF

        print(f"    - Manufacturer ID : 0x{mfg_id:02X}")
        print(f"    - Memory Type     : 0x{mem_type:02X}")
        print(f"    - Capacity ID     : 0x{capacity:02X}")

        # Decode known manufacturers
        mfg_names = {
            0xEF: "Winbond",
            0xC2: "Macronix (MXIC)",
            0x20: "Micron / Numonyx",
            0x1F: "Adesto / Atmel",
            0xC8: "GigaDevice",
            0x85: "Puya",
            0x68: "Boya Micro",
            0x0B: "XTX Technology",
            0x5E: "ZB (ZBIT)",
        }
        name = mfg_names.get(mfg_id, "Unknown")
        cap_bytes = 1 << capacity if 16 <= capacity <= 32 else 0
        cap_mb = cap_bytes / (1024 * 1024) if cap_bytes else 0
        print(f"    -> Flash Identification: {name} (Capacity: {cap_mb:.2f} MB / {cap_bytes} bytes)")

    except Exception as e:
        print(f"[!] Error during test: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
