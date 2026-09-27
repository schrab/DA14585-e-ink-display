#!/usr/bin/env python3
"""
DA14585 Standalone SPI NOR Flash Programmer
============================================
Open-source flash programming and erase utility for Dialog DA14585 / DA14586
using standard ST-Link V2 (SWD) and PyOCD.

Bypasses the requirement for Segger J-Link and ezFlashCLI by using an in-RAM
Cortex-M0 execution stub.

Features:
- Fast block erase (4KB sector 0x20, 64KB block 0xD8, chip erase 0xC7)
- Fast buffered page programming
- Smart flashing (skips already-identical blocks)
- Verification against file data (SHA256 & byte-by-byte)
- Target reset or watchdog retention
"""

import os
import sys
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
    )
except ImportError:
    print("Error: 'pyocd' is required. Run: pip install pyocd", file=sys.stderr)
    sys.exit(1)

# Hardware Registers & Firmware Addresses
SET_FREEZE_REG       = 0x50003300
WATCHDOG_REG         = 0x50003102
SYS_CTRL_REG         = 0x50000012

SPI_INIT_ADDR        = 0x07FCA288  # spi_flash_enable()
SPI_JEDEC_ADDR       = 0x07FC97C4  # spi_flash_read_jedec_id(uint32_t *id_out)
SPI_READ_ADDR        = 0x07FC976C  # spi_flash_read_data(uint8_t *buf, uint32_t addr, uint32_t size, uint32_t *act_size)

# SysRAM4 Scratchpad & Stub Addresses (0x07FD0000 - 0x07FD7FFF)
SCRATCH_BKPT_ADDR    = 0x07FD0000  # bkpt #0 (0xBE00)
SCRATCH_ACTUAL_ADDR  = 0x07FD0100  # uint32_t actual_size
STUB_BASE_ADDR       = 0x07FD0020  # Flash helper binary entry
SCRATCH_BUF_ADDR     = 0x07FD1000  # 4096-byte chunk buffer
SCRATCH_STACK_TOP    = 0x07FD7FE0  # Top of scratch stack

FLASH_ERASE_FN       = 0x07FD0020  # int32_t flash_erase_block(uint32_t address, uint32_t erase_op)
FLASH_WRITE_FN       = 0x07FD008C  # int32_t flash_write(const uint8_t *buf, uint32_t address, uint32_t size)

SECTOR_SIZE_4K       = 4096
BLOCK_SIZE_64K       = 65536
CHUNK_SIZE           = 4096


# Embedded 148-byte Flash Helper Stub (compiled from flash_helper.c)
# Contains flash_erase_block and flash_write with hardware watchdog feeding
FLASH_HELPER_BIN = bytes([
    0xF8, 0xB5, 0xFF, 0x25, 0x11, 0x4C, 0x12, 0x4A, 0x25, 0x80, 0x07, 0x00, 0x0E, 0x00, 0x90, 0x47,
    0x00, 0x28, 0x14, 0xD1, 0x0F, 0x4B, 0x98, 0x47, 0x00, 0x28, 0x13, 0xD1, 0x0E, 0x4B, 0x02, 0x30,
    0x98, 0x47, 0x0E, 0x4B, 0x98, 0x47, 0x3B, 0x02, 0x1B, 0x0A, 0x30, 0x06, 0x18, 0x43, 0x0C, 0x4B,
    0x98, 0x47, 0x0C, 0x4B, 0x98, 0x47, 0x0C, 0x4B, 0x98, 0x47, 0x25, 0x80, 0xF8, 0xBD, 0x01, 0x20,
    0x40, 0x42, 0xFB, 0xE7, 0x02, 0x20, 0x40, 0x42, 0xF8, 0xE7, 0xC0, 0x46, 0x02, 0x31, 0x00, 0x50,
    0x3F, 0x97, 0xFC, 0x07, 0x41, 0x99, 0xFC, 0x07, 0x85, 0x99, 0xFC, 0x07, 0xF9, 0x96, 0xFC, 0x07,
    0xD1, 0x95, 0xFC, 0x07, 0xE5, 0x96, 0xFC, 0x07, 0x5D, 0x98, 0xFC, 0x07, 0x70, 0xB5, 0x00, 0x23,
    0xFF, 0x25, 0x05, 0x4C, 0x82, 0xB0, 0x05, 0x4E, 0x25, 0x80, 0x01, 0x93, 0x01, 0xAB, 0xB0, 0x47,
    0x01, 0x98, 0x25, 0x80, 0x02, 0xB0, 0x70, 0xBD, 0x02, 0x31, 0x00, 0x50, 0x81, 0x98, 0xFC, 0x07
])


def connect_target(frequency: int = 1000000, timeout: float = 15.0):
    """Connect to DA14585 target using ST-Link."""
    probes = ConnectHelper.get_all_connected_probes()
    if not probes:
        raise RuntimeError("No ST-Link debug probe found. Ensure debugger is connected.")

    probe = probes[0]
    session = ConnectHelper.session_with_chosen_probe(
        unique_id=probe.unique_id,
        target_override="cortex_m",
        options={
            "frequency": frequency,
            "connect_mode": "attach",
            "resume_on_disconnect": False,
            "reset_type": "software",
        },
        auto_open=False,
    )
    session.open()
    return session


def execute_subroutine(target: Target, pc_addr: int, r0: int = 0, r1: int = 0, r2: int = 0, r3: int = 0, timeout: float = 5.0) -> int:
    """Execute a function on Cortex-M0 and wait for bkpt #0."""
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
        time.sleep(0.002)

    return target.read_core_register("r0")


class DA14585Flasher:
    def __init__(self, target: Target):
        self.target = target
        self.jedec_id = 0
        self.capacity = 0
        self._init_target()

    def _init_target(self):
        """Halt core, freeze watchdogs, and install RAM helper stub."""
        if not self.target.is_halted():
            self.target.halt()
            time.sleep(0.02)

        # Freeze watchdog and timers
        self.target.write16(SET_FREEZE_REG, 0x000F)

        # Disable interrupts and SysTick so core never wakes into sleep
        self.target.write_core_register("primask", 1)
        self.target.write32(0xE000E180, 0xFFFFFFFF)
        self.target.write32(0xE000E010, 0x00000000)

        # Breakpoint hook in SysRAM4
        self.target.write16(SCRATCH_BKPT_ADDR, 0xBE00)

        # Initialize SPI bus via firmware routine
        execute_subroutine(self.target, SPI_INIT_ADDR)

        # Read JEDEC ID
        self.target.write32(SCRATCH_ACTUAL_ADDR, 0)
        execute_subroutine(self.target, SPI_JEDEC_ADDR, r0=SCRATCH_ACTUAL_ADDR)
        self.jedec_id = self.target.read32(SCRATCH_ACTUAL_ADDR) & 0xFFFFFF

        # Determine flash capacity
        cap_id = self.jedec_id & 0xFF
        if 16 <= cap_id <= 32:
            self.capacity = 1 << cap_id
        else:
            self.capacity = 512 * 1024  # 512 KB default for FM25Q04

        # Install flash helper stub into SysRAM4
        self.target.write_memory_block8(STUB_BASE_ADDR, list(FLASH_HELPER_BIN))

    def read(self, address: int, size: int) -> bytes:
        """Read a block of data from SPI flash."""
        result = bytearray()
        offset = 0
        while offset < size:
            chunk = min(CHUNK_SIZE, size - offset)
            execute_subroutine(
                self.target,
                SPI_READ_ADDR,
                r0=SCRATCH_BUF_ADDR,
                r1=address + offset,
                r2=chunk,
                r3=SCRATCH_ACTUAL_ADDR,
            )
            result.extend(self.target.read_memory_block8(SCRATCH_BUF_ADDR, chunk))
            offset += chunk
            # Pet watchdog
            self.target.write16(WATCHDOG_REG, 0x00FF)
        return bytes(result)

    def erase_sector_4k(self, address: int):
        """Erase a single 4 KB sector (Opcode 0x20)."""
        ret = execute_subroutine(self.target, FLASH_ERASE_FN, r0=address, r1=0x20, timeout=5.0)
        if ret != 0:
            raise RuntimeError(f"Sector erase failed at 0x{address:06X}, error: {ret}")

    def erase_block_64k(self, address: int):
        """Erase a 64 KB block (Opcode 0xD8)."""
        ret = execute_subroutine(self.target, FLASH_ERASE_FN, r0=address, r1=0xD8, timeout=10.0)
        if ret != 0:
            raise RuntimeError(f"64KB block erase failed at 0x{address:06X}, error: {ret}")

    def erase_chip(self):
        """Erase entire SPI NOR flash chip (Opcode 0xC7)."""
        print("[*] Performing Chip Erase (Opcode 0xC7)... This may take ~2-5 seconds...")
        ret = execute_subroutine(self.target, FLASH_ERASE_FN, r0=0, r1=0xC7, timeout=30.0)
        if ret != 0:
            raise RuntimeError(f"Chip erase failed, error: {ret}")

    def write_buffer(self, address: int, data: bytes):
        """Write buffer to SPI flash (up to 4096 bytes per call)."""
        self.target.write_memory_block8(SCRATCH_BUF_ADDR, list(data))
        ret = execute_subroutine(self.target, FLASH_WRITE_FN, r0=SCRATCH_BUF_ADDR, r1=address, r2=len(data))
        if ret != len(data):
            raise RuntimeError(f"Flash write failed at 0x{address:06X}, wrote {ret}/{len(data)} bytes")

    def program(self, address: int, data: bytes, verify: bool = True):
        """Smart-program data to flash: erases only necessary sectors and writes pages."""
        total_len = len(data)
        print("=" * 70)
        print(f"Programming {total_len} bytes to SPI flash at 0x{address:06X}")
        print("=" * 70)

        # 1. Determine sectors to erase
        start_sector = (address // SECTOR_SIZE_4K) * SECTOR_SIZE_4K
        end_sector = ((address + total_len + SECTOR_SIZE_4K - 1) // SECTOR_SIZE_4K) * SECTOR_SIZE_4K
        num_sectors = (end_sector - start_sector) // SECTOR_SIZE_4K

        print(f"[*] Checking {num_sectors} sector(s) (0x{start_sector:06X} - 0x{end_sector:06X})...")

        # Smart Erase: check which sectors actually need erasing
        start_time = time.time()
        for sec in range(start_sector, end_sector, SECTOR_SIZE_4K):
            sec_idx = (sec - start_sector) // SECTOR_SIZE_4K
            sec_existing = self.read(sec, SECTOR_SIZE_4K)

            # Extract corresponding new data slice for this sector
            slice_start = max(0, sec - address)
            slice_end = min(total_len, (sec + SECTOR_SIZE_4K) - address)
            new_slice = data[slice_start:slice_end]

            # Check if sector is already identical
            offset_in_sec = max(0, address - sec)
            existing_target_slice = sec_existing[offset_in_sec : offset_in_sec + len(new_slice)]

            if existing_target_slice == new_slice:
                print(f"  [Sector 0x{sec:06X}] Matches data exactly -> SKIPPING erase & write.")
                continue

            # If not all 0xFF, must erase
            if not all(b == 0xFF for b in sec_existing):
                print(f"  [Sector 0x{sec:06X}] Erasing 4 KB sector... ", end="", flush=True)
                self.erase_sector_4k(sec)
                print("DONE")

            # Write data for this sector
            if len(new_slice) > 0:
                print(f"  [Sector 0x{sec:06X}] Writing {len(new_slice)} bytes... ", end="", flush=True)
                self.write_buffer(address + slice_start, new_slice)
                print("DONE")

        write_time = time.time() - start_time
        print(f"[+] Programming finished in {write_time:.2f}s ({total_len/1024/write_time:.1f} KB/s)")

        # 2. Verification
        if verify:
            print("[*] Verifying written data...")
            read_back = self.read(address, total_len)
            if read_back == data:
                file_hash = hashlib.sha256(data).hexdigest()
                print(f"[SUCCESS] Verification PASSED (SHA256: {file_hash[:16]}...100% bit-exact match)!")
            else:
                mismatches = sum(1 for a, b in zip(data, read_back) if a != b)
                raise RuntimeError(f"Verification FAILED: {mismatches} bytes mismatched!")

    def set_retention_loop(self):
        """Install active watchdog petting loop so chip stays halted without rebooting."""
        RETENTION_STUB_ADDR = 0x07FD0200
        retention_code = [
            0x48, 0x02,  # ldr r0, [pc, #8] (0x50003100)
            0x21, 0xC8,  # movs r1, #0xC8
            0x80, 0x01,  # strh r1, [r0, #0]
            0xE7, 0xFC,  # b .-4
            0x00, 0x31, 0x00, 0x50  # 0x50003100
        ]
        self.target.write_memory_block8(RETENTION_STUB_ADDR, retention_code)
        self.target.write_core_register("pc", RETENTION_STUB_ADDR | 1)
        self.target.resume()
        print("[*] Board placed in low-power watchdog retention loop.")


def main():
    parser = argparse.ArgumentParser(description="DA14585 SPI NOR Flash Programmer (SWD via ST-Link)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Write command
    p_write = subparsers.add_parser("write", help="Write binary file to SPI flash")
    p_write.add_argument("file", help="Binary file to write (.bin)")
    p_write.add_argument("--addr", type=lambda x: int(x, 0), default=0x004000, help="Flash offset (default: 0x004000 for App Image 1)")
    p_write.add_argument("--no-verify", action="store_true", help="Skip read-back verification")
    p_write.add_argument("--reset", action="store_true", help="Reset target to execute new firmware immediately")

    # Erase command
    p_erase = subparsers.add_parser("erase", help="Erase SPI flash sectors")
    p_erase.add_argument("--addr", type=lambda x: int(x, 0), default=0x004000, help="Starting flash offset")
    p_erase.add_argument("--size", type=lambda x: int(x, 0), default=4096, help="Erase size in bytes (multiple of 4KB)")
    p_erase.add_argument("--chip", action="store_true", help="Erase entire flash chip")

    # Read / Dump command
    p_read = subparsers.add_parser("read", help="Read SPI flash content to file")
    p_read.add_argument("file", help="Destination file path")
    p_read.add_argument("--addr", type=lambda x: int(x, 0), default=0x000000, help="Starting flash offset")
    p_read.add_argument("--size", type=lambda x: int(x, 0), default=524288, help="Read size in bytes (default: 512KB)")

    # Verify command
    p_verify = subparsers.add_parser("verify", help="Verify flash content against binary file")
    p_verify.add_argument("file", help="Binary file to compare against")
    p_verify.add_argument("--addr", type=lambda x: int(x, 0), default=0x004000, help="Flash offset")

    # Common options
    parser.add_argument("--freq", type=int, default=1000000, help="SWD clock frequency in Hz (default 1 MHz)")
    args = parser.parse_args()

    session = connect_target(frequency=args.freq)
    target = session.target

    try:
        flasher = DA14585Flasher(target)
        print(f"[+] Connected to DA14585 (Flash ID: 0x{flasher.jedec_id:06X}, Capacity: {flasher.capacity/1024:.0f} KB)")

        if args.command == "write":
            if not os.path.exists(args.file):
                print(f"Error: File '{args.file}' not found!", file=sys.stderr)
                sys.exit(1)
            with open(args.file, "rb") as f:
                data = f.read()
            flasher.program(args.addr, data, verify=not args.no_verify)
            if args.reset:
                print("[*] Performing software reset...")
                target.reset()
                target.resume()
                print("[+] Reset complete, target running.")
            else:
                flasher.set_retention_loop()

        elif args.command == "erase":
            if args.chip:
                flasher.erase_chip()
            else:
                start_sec = (args.addr // SECTOR_SIZE_4K) * SECTOR_SIZE_4K
                end_sec = ((args.addr + args.size + SECTOR_SIZE_4K - 1) // SECTOR_SIZE_4K) * SECTOR_SIZE_4K
                for sec in range(start_sec, end_sec, SECTOR_SIZE_4K):
                    print(f"[*] Erasing 4 KB sector at 0x{sec:06X}... ", end="", flush=True)
                    flasher.erase_sector_4k(sec)
                    print("DONE")
            flasher.set_retention_loop()

        elif args.command == "read":
            print(f"[*] Reading {args.size} bytes from 0x{args.addr:06X} -> {args.file}...")
            data = flasher.read(args.addr, args.size)
            with open(args.file, "wb") as f:
                f.write(data)
            print(f"[+] Successfully saved {len(data)} bytes to {args.file}")
            flasher.set_retention_loop()

        elif args.command == "verify":
            with open(args.file, "rb") as f:
                expected = f.read()
            print(f"[*] Comparing flash at 0x{args.addr:06X} against {args.file} ({len(expected)} bytes)...")
            actual = flasher.read(args.addr, len(expected))
            if actual == expected:
                print("[SUCCESS] Flash content is 100% IDENTICAL to file!")
            else:
                diffs = sum(1 for a, b in zip(expected, actual) if a != b)
                print(f"[FAILED] Mismatches detected: {diffs}/{len(expected)} bytes differ!")
            flasher.set_retention_loop()

    finally:
        session.close()


if __name__ == "__main__":
    main()
