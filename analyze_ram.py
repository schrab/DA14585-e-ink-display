"""
Analyze DA14585 96KB SysRAM Dump
===============================
Extracts:
1. ASCII & UTF-8 strings (BLE names, SDK signatures, E-Ink drivers, SPI strings)
2. Peripheral register references (GPIO 0x500030xx, SPI 0x500012xx, etc.)
3. Known BLE GATT services and Dialog SDK structures
"""

import sys
import re
import struct

RAM_BASE = 0x07FC0000
BIN_FILE = "da14585_full_ram_96k.bin"

def extract_strings(data, min_len=4):
    """Find all printable ASCII strings."""
    pattern = rb"[\x20-\x7E]{" + str(min_len).encode() + rb",}"
    for match in re.finditer(pattern, data):
        offset = match.start()
        addr = RAM_BASE + offset
        s = match.group().decode("latin1")
        yield addr, offset, s

def search_peripheral_literals(data):
    """Search for 32-bit words that point to DA14585 hardware registers."""
    registers = {
        0x50000010: "PMU_CTRL_REG",
        0x50000012: "SYS_CTRL_REG",
        0x50000014: "CLK_CTRL_REG",
        0x50000016: "CLK_PER_REG",
        0x50001200: "SPI_CTRL_REG",
        0x50001202: "SPI_RX_TX_REG0",
        0x50001208: "SPI_CTRL_REG1",
        0x50003000: "GPIO_BASE / P0_DATA",
        0x50003006: "P00_MODE_REG",
        0x50003008: "P01_MODE_REG",
        0x5000300A: "P02_MODE_REG",
        0x5000300C: "P03_MODE_REG",
        0x5000300E: "P04_MODE_REG",
        0x50003010: "P05_MODE_REG",
        0x50003012: "P06_MODE_REG",
        0x50003014: "P07_MODE_REG",
        0x50003026: "P10_MODE_REG",
        0x50003028: "P11_MODE_REG",
        0x5000302A: "P12_MODE_REG",
        0x5000302C: "P13_MODE_REG",
        0x5000302E: "P14_MODE_REG",
        0x50003100: "TIMER0_ON_REG",
        0x50003102: "WATCHDOG_REG",
        0x50003300: "SET_FREEZE_REG",
    }
    found = []
    for offset in range(0, len(data) - 3, 4):
        val = struct.unpack_from("<I", data, offset)[0]
        if val in registers:
            found.append((RAM_BASE + offset, registers[val], hex(val)))
        elif 0x50003000 <= val <= 0x50003080:
            found.append((RAM_BASE + offset, f"GPIO_REG (0x{val:08X})", hex(val)))
        elif 0x50001200 <= val <= 0x50001210:
            found.append((RAM_BASE + offset, f"SPI_REG (0x{val:08X})", hex(val)))
    return found

def main():
    try:
        with open(BIN_FILE, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        print(f"Error: {BIN_FILE} not found.")
        return

    print("=" * 70)
    print(f"DA14585 SysRAM Dump Analysis: {BIN_FILE} ({len(data)} bytes)")
    print("=" * 70)

    # 1. Search for Interesting Strings
    keywords = [
        "sdk", "dialog", "da14", "ble", "gatt", "adv", "epd", "eink", "ink",
        "disp", "spi", "flash", "screen", "font", "image", "lut", "paint",
        "ssd", "uc81", "il03", "gdey", "gdew", "wf", "panel", "batt", "temp"
    ]
    print("\n[+] Notable Strings Identified:")
    interesting_strings = []
    all_strings = list(extract_strings(data, min_len=4))
    for addr, offset, s in all_strings:
        lower_s = s.lower()
        if any(kw in lower_s for kw in keywords) or len(s) >= 12:
            interesting_strings.append((addr, s))

    if interesting_strings:
        for addr, s in interesting_strings[:50]:
            print(f"  0x{addr:08X}: {s}")
        if len(interesting_strings) > 50:
            print(f"  ... and {len(interesting_strings) - 50} more.")
    else:
        print("  No obvious high-level keyword strings found.")

    # 2. Search for Peripheral Register References
    print("\n[+] Hardware Register Literal Pools in Code:")
    reg_refs = search_peripheral_literals(data)
    for addr, name, hex_val in reg_refs[:30]:
        print(f"  0x{addr:08X} -> {name} ({hex_val})")
    if len(reg_refs) > 30:
        print(f"  ... and {len(reg_refs) - 30} more references.")

    # 3. Memory Section Estimation
    print("\n[+] SysRAM Cell Utilization:")
    cells = [
        ("SysRAM1 (Application/Vectors)", 0, 32 * 1024),
        ("SysRAM2 (BLE Stack/Exchange)", 32 * 1024, 16 * 1024),
        ("SysRAM3 (Data/Stack)", 48 * 1024, 16 * 1024),
        ("SysRAM4 (High RAM/Heap)", 64 * 1024, 32 * 1024),
    ]
    for name, start, size in cells:
        chunk = data[start : start + size]
        non_zero = sum(1 for b in chunk if b != 0 and b != 0xFF)
        pct = (non_zero / size) * 100
    # 4. Search for all EINK and display related strings
    print("\n[+] Detailed Display & Bluetooth Strings:")
    for addr, offset, s in all_strings:
        if any(w in s for w in ["EINK", "Font", "v_6", "14585", "42000"]):
            print(f"  0x{addr:08X} (offset +0x{offset:05X}): {s}")

    # 5. Inspect bytes around SPI register references
    print("\n[+] Disassembly around SPI Controller (0x50001200) references:")
    try:
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
        for ref_addr, name, hex_val in reg_refs:
            if "SPI" in name:
                print(f"\n--- Code referencing {name} near 0x{ref_addr:08X} ---")
                # Look 32 bytes before and after
                ref_offset = ref_addr - RAM_BASE
                window_start = max(0, ref_offset - 40)
                window_len = 80
                chunk = data[window_start : window_start + window_len]
                base_pc = RAM_BASE + window_start
                for ins in md.disasm(chunk, base_pc):
                    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")
    except ImportError:
        print("  Capstone not available for disassembly.")

if __name__ == "__main__":
    main()
