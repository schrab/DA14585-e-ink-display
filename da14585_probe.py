"""
DA14585 SWD Hardware Testing & RAM Dump Tool
===========================================
Reverse-engineering diagnostic script for Dialog Semiconductor DA14585 (ARM Cortex-M0).
Communicates via ST-Link V2 over SWD using pyOCD.

Hardware context:
- DA14585 has active-HIGH reset; ST-Link NRST pin is disconnected.
- DA14585 frequently enters low-power sleep modes where SWD power domain (PD_DBG) is off.
- This script implements aggressive retry connection loops and freezes the hardware watchdog.
"""

import sys
import time
import argparse
import logging
from typing import Optional, List, Dict

try:
    from pyocd.core.helpers import ConnectHelper
    from pyocd.core.target import Target
    from pyocd.core.exceptions import (
        Error as PyOCDError,
        ProbeError,
        TransferError,
        TransferTimeoutError,
        CoreRegisterAccessError,
    )
except ImportError as err:
    print(f"Error importing 'pyocd': {err}. Please install via: pip install pyocd", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("DA14585_Probe")

# ==============================================================================
# DA14585 Memory Map & Hardware Register Definitions
# ==============================================================================
SYSRAM_BASE         = 0x07FC0000  # SysRAM Cell 1 Base (32KB: 0x07FC0000 - 0x07FC7FFF)
SYSRAM_TOTAL_SIZE   = 96 * 1024   # Total SysRAM = 96KB (Cells 1 to 4)

# Power & Clock Management Registers
PMU_CTRL_REG        = 0x50000010  # Power Management Unit Control
SYS_CTRL_REG        = 0x50000012  # System Control Register (Debugger enable, Remap)
CLK_CTRL_REG        = 0x50000014  # Clock Control Register

# Watchdog & Freeze Registers
WATCHDOG_REG        = 0x50003102  # Watchdog Timer reload/counter register
SET_FREEZE_REG      = 0x50003300  # Freeze register (bit 3 = FRZ_WDOG)
RESET_FREEZE_REG    = 0x50003302  # Unfreeze register
FRZ_WDOG_BIT        = (1 << 3)    # Bit 3: Freezes watchdog countdown when CPU halted

# System Control Register Bits
DEBUGGER_ENABLE_BIT = (1 << 15)   # Bit 15: Forces SWD debug block awake


def format_hex_dump(data: bytes, base_address: int = 0x0) -> str:
    """Format a byte array into a classic 16-bytes-per-line hex dump."""
    lines = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hex_parts = []
        for i, b in enumerate(chunk):
            hex_parts.append(f"{b:02X}")
            if i == 7:
                hex_parts.append("")  # Additional separator between 8-byte halves
        hex_str = " ".join(hex_parts).ljust(49)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"0x{base_address + offset:08X}  {hex_str}  |{ascii_str}|")
    return "\n".join(lines)


def freeze_watchdog(target: Target) -> bool:
    """
    Freeze the DA14585 hardware watchdog timer.
    
    If the Cortex-M0 core is halted over SWD, the DA14585 watchdog will continue
    counting down and fire an NMI or system reset unless frozen via SET_FREEZE_REG.
    """
    try:
        # Read current freeze register
        current_freeze = target.read16(SET_FREEZE_REG)
        # Write freeze bit for watchdog
        target.write16(SET_FREEZE_REG, current_freeze | FRZ_WDOG_BIT)
        # Also touch WATCHDOG_REG to reload max count
        target.write16(WATCHDOG_REG, 0x00FF)
        print("[+] Hardware Watchdog timer frozen successfully (SET_FREEZE_REG |= 0x08).")
        return True
    except Exception as ex:
        print(f"[!] Warning: Could not freeze watchdog timer: {ex}")
        return False


def establish_swd_connection(
    target_type: str = "cortex_m",
    frequency_hz: int = 1000000,
    timeout_seconds: float = 15.0,
    retry_delay_seconds: float = 0.2,
):
    """
    Establish an SWD connection via ST-Link with retry logic and fallback frequencies.
    
    DA14585 deep sleep and active-high reset mean the target might only be accessible
    briefly during boot or wake-up interrupts.
    """
    print("=" * 70)
    print("DA14585 SWD Connection Initiator")
    print(f"Target Type: {target_type} | SWD Clock: {frequency_hz / 1000:.1f} kHz | Timeout: {timeout_seconds}s")
    print("Note: ST-Link NRST is disconnected (DA14585 RST is Active-HIGH).")
    print("=" * 70)

    # First, verify ST-Link probe presence
    probes = ConnectHelper.get_all_connected_probes()
    if not probes:
        raise RuntimeError("No debug probe detected! Check USB connection to the ST-Link V2.")

    probe = probes[0]
    print(f"[+] Found Debug Probe: {probe.description} (Serial: {probe.unique_id})")

    frequencies_to_try = [frequency_hz]
    if frequency_hz > 500000:
        frequencies_to_try.append(500000)
    if 100000 not in frequencies_to_try:
        frequencies_to_try.append(100000)

    start_time = time.time()
    attempt = 0

    while time.time() - start_time < timeout_seconds:
        attempt += 1
        current_freq = frequencies_to_try[(attempt - 1) % len(frequencies_to_try)]
        elapsed = time.time() - start_time

        print(
            f"[*] [Attempt {attempt} | {elapsed:.1f}s/{timeout_seconds:.1f}s] "
            f"Connecting at {current_freq / 1000:.0f} kHz... ",
            end="",
            flush=True,
        )

        session = None
        try:
            # We configure attach mode without hardware reset assertion
            session = ConnectHelper.session_with_chosen_probe(
                unique_id=probe.unique_id,
                target_override=target_type,
                options={
                    "frequency": current_freq,
                    "connect_mode": "attach",
                    "resume_on_disconnect": False,
                    "reset_type": "software",
                },
                auto_open=False,
            )

            # Explicitly open session to catch probe/SWD handshake errors
            session.open()

            # Test target access by reading target state
            target = session.target
            if not target or not target.cores:
                raise ProbeError("Target core not detected.")

            state = target.get_state()
            print(f"SUCCESS! Target State: {state.name}")
            return session

        except (ProbeError, TransferError, TransferTimeoutError, PyOCDError, KeyError, Exception) as ex:
            if session:
                try:
                    session.close()
                except Exception:
                    pass
            print(f"Waiting... ({type(ex).__name__}: {ex})")
            time.sleep(retry_delay_seconds)

        except KeyboardInterrupt:
            print("\n[!] Connection aborted by user.")
            if session:
                session.close()
            sys.exit(1)

    print("\n" + "!" * 70)
    print("[ERROR] Connection timed out after multiple attempts.")
    print("Troubleshooting DA14585 SWD:")
    print("1. Target Power: Verify 3.3V and GND are firmly connected and board is powered.")
    print("2. Sleep Mode: DA14585 shuts down PD_DBG (Debug Power Domain) in Extended Sleep.")
    print("   -> TIP: Run this script and immediately POWER-CYCLE or pulse RST high to 3.3V.")
    print("   -> The internal Boot ROM runs for ~100ms on boot, allowing SWD attachment.")
    print("3. Pinout: Verify SWCLK and SWDIO test pads (typically P1_4/P1_3 or dedicated pads).")
    print("!" * 70)
    return None


def read_and_display_registers(target: Target) -> Dict[str, int]:
    """Halt core and print Cortex-M0 CPU registers."""
    print("\n" + "=" * 70)
    print("CORTEX-M0 CORE REGISTERS")
    print("=" * 70)

    if not target.is_halted():
        print("[*] Halting Cortex-M0 core...")
        target.halt()
        time.sleep(0.05)

    # Freeze watchdog immediately upon halting
    freeze_watchdog(target)

    core_regs = [
        "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
        "r8", "r9", "r10", "r11", "r12", "sp", "lr", "pc", "xpsr"
    ]

    reg_values = {}
    for r in core_regs:
        try:
            val = target.read_core_register(r)
            reg_values[r] = val
        except CoreRegisterAccessError:
            reg_values[r] = 0xDEADBEEF

    # Display registers in 4-column layout
    for i in range(0, 16, 4):
        chunk = core_regs[i : i + 4]
        line = "  ".join(f"{r.upper():>4}: 0x{reg_values[r]:08X}" for r in chunk)
        print(line)
    
    # Display xPSR details
    xpsr = reg_values.get("xpsr", 0)
    thumb_bit = (xpsr >> 24) & 1
    ipsr = xpsr & 0x3F
    print(f"{'XPSR':>4}: 0x{xpsr:08X} (T-bit: {thumb_bit}, Exception/ISR: {ipsr})")
    print("=" * 70)
    return reg_values


def dump_internal_ram(
    target: Target,
    start_address: int = SYSRAM_BASE,
    dump_size: int = 1024,
    output_bin_path: Optional[str] = None,
) -> bytes:
    """Read a block of internal RAM and print formatted hex dump."""
    print("\n" + "=" * 70)
    print(f"INTERNAL RAM DUMP: 0x{start_address:08X} - 0x{start_address + dump_size - 1:08X} ({dump_size} bytes)")
    print("=" * 70)

    raw_data = bytes(target.read_memory_block8(start_address, dump_size))
    print(format_hex_dump(raw_data, base_address=start_address))
    print("=" * 70)

    # Vector Table Analysis for DA14585 SysRAM Cell 1
    if start_address == SYSRAM_BASE and len(raw_data) >= 16:
        initial_sp = int.from_bytes(raw_data[0:4], "little")
        reset_vector = int.from_bytes(raw_data[4:8], "little")
        nmi_vector = int.from_bytes(raw_data[8:12], "little")
        hardfault_vector = int.from_bytes(raw_data[12:16], "little")

        print("\n[+] Vector Table Analysis (from SysRAM 0x07FC0000):")
        print(f"    - Initial Stack Pointer (SP) : 0x{initial_sp:08X}")
        print(f"    - Reset Handler Vector       : 0x{reset_vector:08X}")
        print(f"    - NMI Handler Vector         : 0x{nmi_vector:08X}")
        print(f"    - HardFault Handler Vector   : 0x{hardfault_vector:08X}")

        # Check if SP points into valid SysRAM range (0x07FC0000 - 0x07FD8000)
        if 0x07FC0000 <= initial_sp <= 0x07FD8000:
            print("    [OK] Initial SP is valid and points within DA14585 96KB SysRAM.")
        else:
            print("    [!] Note: Initial SP is outside standard SysRAM bounds (RAM may be uninitialized).")

    if output_bin_path:
        with open(output_bin_path, "wb") as f:
            f.write(raw_data)
        print(f"[+] Saved binary memory dump to: {output_bin_path}")

    return raw_data


def main():
    parser = argparse.ArgumentParser(
        description="DA14585 SWD Hardware Testing & Memory Inspection Tool"
    )
    parser.add_argument(
        "--freq",
        type=int,
        default=1000000,
        help="SWD clock frequency in Hz (default: 1000000 / 1MHz)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Connection timeout in seconds (default: 15.0s)",
    )
    parser.add_argument(
        "--addr",
        type=lambda x: int(x, 0),
        default=SYSRAM_BASE,
        help="RAM start address in hex (default: 0x07FC0000)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=1024,
        help="Number of bytes to dump (default: 1024)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="da14585_ram_dump_0x07fc0000.bin",
        help="Output binary file path for RAM dump",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume target execution before exiting (default: keep halted)",
    )

    args = parser.parse_args()

    session = establish_swd_connection(
        target_type="cortex_m",
        frequency_hz=args.freq,
        timeout_seconds=args.timeout,
    )

    if session is None:
        sys.exit(1)

    try:
        target = session.target

        # Step 1: Halt core and read registers
        read_and_display_registers(target)

        # Step 2: Dump internal RAM
        dump_internal_ram(
            target=target,
            start_address=args.addr,
            dump_size=args.size,
            output_bin_path=args.out,
        )

        if args.resume:
            print("[*] Resuming target CPU core...")
            target.resume()
        else:
            print("[*] Target remains halted under debugger control.")

    finally:
        print("[*] Closing SWD session...")
        session.close()
        print("[+] Done.")


if __name__ == "__main__":
    main()
