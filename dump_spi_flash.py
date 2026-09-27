"""
DA14585 External SPI NOR Flash Dumper (Phase 2)
==============================================
Extracts the complete external SPI NOR flash image from a Dialog DA14585 board
using SWD execution injection into SysRAM4.

Hardware configuration verified:
- SPI CS   : P0_3 (Active Low)
- SPI CLK  : P0_0 (PID_SPI_CLK)
- SPI MOSI : P0_6 (PID_SPI_DO)
- SPI MISO : P0_5 (PID_SPI_DI)
"""

import sys
import os
import time
import hashlib
import argparse
from typing import Optional, Tuple

try:
    from pyocd.core.helpers import ConnectHelper
    from pyocd.core.target import Target
    from pyocd.core.exceptions import (
        Error as PyOCDError,
        ProbeError,
        TransferError,
        TransferTimeoutError,
    )
except ImportError:
    print("Error: 'pyocd' is required. Run: pip install pyocd", file=sys.stderr)
    sys.exit(1)

# Hardware & Firmware Constants
SET_FREEZE_REG       = 0x50003300
WATCHDOG_REG         = 0x50003102
FRZ_WDOG_BIT         = (1 << 3)

# Verified Function entry points in SysRAM1
SPI_INIT_ADDR        = 0x07FCA288  # spi_flash_enable() / pinmux configuration
SPI_JEDEC_ADDR       = 0x07FC97C4  # spi_flash_read_jedec_id(uint32_t *id_out)
SPI_READ_ADDR        = 0x07FC976C  # spi_flash_read_data(uint8_t *buf, uint32_t addr, uint32_t size, uint32_t *act_size)

# Memory Scratchpad in SysRAM4 (0x07FD0000 - 0x07FD7FFF)
SCRATCH_BKPT_ADDR    = 0x07FD0000  # Holds bkpt #0 (0xBE00)
SCRATCH_ACTUAL_ADDR  = 0x07FD0100  # uint32_t actual_size
SCRATCH_BUF_ADDR     = 0x07FD1000  # 4096-byte chunk buffer
SCRATCH_STACK_TOP    = 0x07FD7FE0  # Top of scratch stack

DEFAULT_CHUNK_SIZE   = 4096        # 4 KB per SWD block transfer


def connect_target(frequency: int = 1000000, timeout: float = 20.0):
    """Establish SWD connection to the DA14585."""
    print("=" * 70)
    print("DA14585 SPI Flash Extraction Tool (Phase 2)")
    print(f"SWD Frequency: {frequency / 1000:.0f} kHz | Timeout: {timeout:.0f}s")
    print("=" * 70)

    probes = ConnectHelper.get_all_connected_probes()
    if not probes:
        raise RuntimeError("No debug probe detected. Ensure ST-Link V2 is plugged in.")

    probe = probes[0]
    print(f"[+] Debug Probe: {probe.description} (Serial: {probe.unique_id})")

    frequencies = [frequency]
    if frequency > 500000:
        frequencies.append(500000)
    if 100000 not in frequencies:
        frequencies.append(100000)

    start = time.time()
    attempt = 0
    while time.time() - start < timeout:
        attempt += 1
        cur_freq = frequencies[(attempt - 1) % len(frequencies)]
        print(f"[*] [Attempt {attempt}] Connecting at {cur_freq/1000:.0f} kHz... ", end="", flush=True)

        session = None
        try:
            session = ConnectHelper.session_with_chosen_probe(
                unique_id=probe.unique_id,
                target_override="cortex_m",
                options={
                    "frequency": cur_freq,
                    "connect_mode": "attach",
                    "resume_on_disconnect": False,
                    "reset_type": "software",
                },
                auto_open=False,
            )
            session.open()
            target = session.target
            if not target or not target.cores:
                raise ProbeError("Target core not ready.")
            print(f"SUCCESS! Target State: {target.get_state().name}")
            return session
        except Exception as e:
            if session:
                try:
                    session.close()
                except Exception:
                    pass
            print(f"Waiting... ({type(e).__name__})")
            time.sleep(0.2)

    raise TimeoutError("Could not connect to target within timeout window.")


def execute_subroutine(target: Target, pc_addr: int, r0: int = 0, r1: int = 0, r2: int = 0, r3: int = 0, timeout: float = 2.0):
    """Execute a function on the Cortex-M0 core and wait for it to hit bkpt #0."""
    target.write_core_register("r0", r0)
    target.write_core_register("r1", r1)
    target.write_core_register("r2", r2)
    target.write_core_register("r3", r3)
    target.write_core_register("sp", SCRATCH_STACK_TOP)
    target.write_core_register("lr", SCRATCH_BKPT_ADDR | 1)
    target.write_core_register("pc", pc_addr | 1)
    target.write_core_register("xpsr", 0x01000000)
    target.resume()

    start = time.time()
    while not target.is_halted():
        if time.time() - start > timeout:
            target.halt()
            raise TimeoutError(f"Subroutine at 0x{pc_addr:08X} timed out after {timeout}s.")
        time.sleep(0.001)


def read_jedec_id(target: Target) -> Tuple[int, int, int, int]:
    """Read the 3-byte JEDEC ID from the external SPI flash."""
    target.write32(SCRATCH_ACTUAL_ADDR, 0x00000000)
    execute_subroutine(target, SPI_JEDEC_ADDR, r0=SCRATCH_ACTUAL_ADDR)
    raw_id = target.read32(SCRATCH_ACTUAL_ADDR)

    mfg_id = (raw_id >> 16) & 0xFF
    mem_type = (raw_id >> 8) & 0xFF
    capacity_id = raw_id & 0xFF

    if 16 <= capacity_id <= 32:
        capacity_bytes = 1 << capacity_id
    else:
        capacity_bytes = 512 * 1024  # Default fallback 512 KB

    return raw_id, mfg_id, mem_type, capacity_bytes


def dump_flash(target: Target, total_size: int, chunk_size: int = DEFAULT_CHUNK_SIZE, output_path: str = "da14585_spi_flash.bin", resume: bool = False):
    """Dump entire SPI flash to disk using chunked read loop."""
    start_offset = 0
    file_mode = "wb"

    if resume and os.path.exists(output_path):
        existing_len = os.path.getsize(output_path)
        # Align to chunk_size
        start_offset = (existing_len // chunk_size) * chunk_size
        if start_offset > 0:
            print(f"[+] Resuming dump from offset 0x{start_offset:06X} ({start_offset / 1024:.0f} KB already dumped)")
            file_mode = "r+b"

    print("\n" + "=" * 70)
    print(f"Dumping SPI Flash: {total_size} bytes ({total_size / 1024:.0f} KB) -> {output_path}")
    print(f"Block Size: {chunk_size} bytes | Starting Offset: 0x{start_offset:06X}")
    print("=" * 70)

    hasher = hashlib.sha256()
    start_time = time.time()
    total_bytes_read = 0

    with open(output_path, file_mode) as f_out:
        if start_offset > 0:
            f_out.seek(start_offset)
            # Hash existing content up to start_offset
            with open(output_path, "rb") as f_prev:
                hasher.update(f_prev.read(start_offset))

        for offset in range(start_offset, total_size, chunk_size):
            block_len = min(chunk_size, total_size - offset)

            # Reload watchdog timer on each block to prevent watchdog reset/NMI
            target.write16(WATCHDOG_REG, 0x00FF)

            # Call spi_flash_read_data(buf, offset, block_len, &actual_size)
            execute_subroutine(
                target,
                SPI_READ_ADDR,
                r0=SCRATCH_BUF_ADDR,
                r1=offset,
                r2=block_len,
                r3=SCRATCH_ACTUAL_ADDR,
                timeout=5.0,
            )

            # Block-read data from SysRAM4
            chunk = bytes(target.read_memory_block8(SCRATCH_BUF_ADDR, block_len))
            f_out.write(chunk)
            hasher.update(chunk)
            total_bytes_read += len(chunk)

            # Progress Reporting
            pct = (total_bytes_read / total_size) * 100
            elapsed = time.time() - start_time
            speed_kb = (total_bytes_read / 1024) / elapsed if elapsed > 0 else 0
            eta = (total_size - total_bytes_read) / (speed_kb * 1024) if speed_kb > 0 else 0

            preview = chunk[:8].hex(" ")
            print(
                f"\r[{pct:5.1f}%] 0x{offset:06X}/0x{total_size:06X} "
                f"({speed_kb:5.1f} KB/s | ETA: {eta:3.1f}s) -> [{preview}]",
                end="",
                flush=True,
            )

    total_time = time.time() - start_time
    avg_speed = (total_bytes_read / 1024) / total_time
    sha256_hex = hasher.hexdigest()

    print("\n" + "=" * 70)
    print(f"[+] Flash Dump Complete in {total_time:.2f} seconds ({avg_speed:.1f} KB/s)!")
    print(f"[+] Output File  : {output_path} ({os.path.getsize(output_path)} bytes)")
    print(f"[+] SHA256 Hash  : {sha256_hex}")
    print("=" * 70)

    # Validate Dialog Boot Header
    with open(output_path, "rb") as f:
        header = f.read(64)
    magic = header[:2]
    if magic == b"\x70\x50":
        print("[+] Validated Dialog Single-Image SPI Boot Header (Magic: 0x70 0x50)")
    elif magic in (b"\x70\x60", b"\x70\x61"):
        print("[+] Validated Dialog Multi-Image SPI Boot Header (Magic: 0x70 0x60/61)")
    else:
        print(f"[!] Warning: Non-standard Boot Header Magic: {magic.hex()}")

    return sha256_hex


def main():
    parser = argparse.ArgumentParser(description="DA14585 SPI NOR Flash Extraction Tool")
    parser.add_argument("--size", type=lambda x: int(x, 0), default=None, help="Custom dump size in bytes")
    parser.add_argument("--out", type=str, default="da14585_spi_flash.bin", help="Output binary file path")
    parser.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE, help="Chunk size in bytes (default 4096)")
    parser.add_argument("--freq", type=int, default=1000000, help="SWD clock frequency in Hz")
    parser.add_argument("--timeout", type=float, default=20.0, help="Connection timeout in seconds")
    parser.add_argument("--resume", action="store_true", help="Resume previous partial dump if available")
    args = parser.parse_args()

    session = connect_target(frequency=args.freq, timeout=args.timeout)
    target = session.target

    try:
        if not target.is_halted():
            target.halt()
            time.sleep(0.05)

        # 1. Freeze all watchdogs and system timers
        target.write16(SET_FREEZE_REG, 0x000F)

        # 2. Disable all NVIC interrupts and SysTick so core NEVER vectors away to sleep
        target.write_core_register("primask", 1)
        target.write32(0xE000E180, 0xFFFFFFFF)  # NVIC_ICER: Disable all interrupts
        target.write32(0xE000E280, 0xFFFFFFFF)  # NVIC_ICPR: Clear all pending
        target.write32(0xE000E010, 0x00000000)  # SYST_CSR: Disable SysTick timer

        print("[+] Core halted, Watchdog/Timers frozen, Interrupts & SysTick disabled.")

        # Setup breakpoint hook in SysRAM4
        target.write16(SCRATCH_BKPT_ADDR, 0xBE00)  # bkpt #0

        # Initialize SPI controller and GPIO pins
        print("[*] Initializing SPI bus (spi_flash_enable at 0x07FCA288)...")
        execute_subroutine(target, SPI_INIT_ADDR)
        print("[+] SPI Peripheral initialized (CS=P0_3, CLK=P0_0, MOSI=P0_6, MISO=P0_5).")

        # Read JEDEC ID
        raw_id, mfg, mem_type, cap = read_jedec_id(target)
        mfg_names = {
            0xA1: "Fudan Microelectronics (FM25Q04/FM25Q08)",
            0xEF: "Winbond",
            0xC2: "Macronix (MXIC)",
            0xC8: "GigaDevice",
            0x85: "Puya Semiconductor",
            0x5E: "Zbit Semiconductor",
            0x68: "Boya Microelectronics",
        }
        mfg_str = mfg_names.get(mfg, f"Unknown (0x{mfg:02X})")
        print(f"[+] JEDEC ID: 0x{raw_id:06X} (Mfg: {mfg_str}, Type: 0x{mem_type:02X}, Cap: {cap/1024:.0f} KB)")

        dump_size = args.size if args.size is not None else cap
        dump_flash(target, total_size=dump_size, chunk_size=args.chunk, output_path=args.out, resume=args.resume)

    finally:
        print("[*] Closing SWD session...")
        session.close()
        print("[+] Done.")


if __name__ == "__main__":
    main()
