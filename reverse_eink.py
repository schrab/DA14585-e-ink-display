"""
Reverse-Engineering DA14585 E-Ink Display Drivers & Pinout
==========================================================
Analyzes da14585_fw_image1.bin (loaded at 0x07FC0000) to extract:
1. All GPIO configurations (set_pad_functions / GPIO_ConfigurePin)
2. E-Ink controller IC detection (commands, init sequences)
3. Waveform LUT structures from flash (0x2E000)
"""

import struct
import capstone

FW_BIN = "da14585_fw_image1.bin"
FLASH_BIN = "da14585_spi_flash_512k.bin"
FW_BASE = 0x07FC0000

def analyze_gpio_configurations():
    with open(FW_BIN, "rb") as f:
        data = f.read()

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

    print("=" * 70)
    print("1. SCANNING ALL GPIO CONFIGURATIONS IN FIRMWARE")
    print("=" * 70)

    # Search for calls to GPIO_ConfigurePin (0x07FC2E2C)
    # In Thumb: BL instruction
    gpio_calls = []
    target_addr = 0x07FC2E2C

    for offset in range(0, len(data) - 4, 2):
        w1, w2 = struct.unpack_from("<HH", data, offset)
        if (w1 & 0xF800) == 0xF000 and (w2 & 0xD800) == 0xD000:
            s = (w1 >> 10) & 1
            imm10 = w1 & 0x3FF
            j1 = (w2 >> 13) & 1
            j2 = (w2 >> 11) & 1
            imm11 = w2 & 0x7FF
            i1 = not (j1 ^ s)
            i2 = not (j2 ^ s)
            imm25 = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
            if imm25 & (1 << 24):
                imm25 -= (1 << 25)
            pc = FW_BASE + offset + 4
            dest = pc + imm25
            if dest == target_addr:
                gpio_calls.append(pc - 4)

    print(f"[+] Found {len(gpio_calls)} direct calls to GPIO_ConfigurePin (0x{target_addr:08X}):")
    for call_pc in gpio_calls:
        # Disassemble 20 bytes preceding the call
        call_offset = call_pc - FW_BASE
        start_offset = max(0, call_offset - 24)
        chunk = data[start_offset : call_offset + 4]
        chunk_base = FW_BASE + start_offset
        print(f"\n--- Caller at 0x{call_pc:08X} ---")
        for ins in md.disasm(chunk, chunk_base):
            print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

def analyze_eink_lut():
    with open(FLASH_BIN, "rb") as f:
        flash_data = f.read()

    print("\n" + "=" * 70)
    print("2. E-INK LOOKUP TABLE (LUT) / WAVEFORM ANALYSIS")
    print("=" * 70)

    # Flash offset 0x02E000 - 0x02F000
    lut_chunk = flash_data[0x2E000:0x2F000]
    print(f"[+] Inspecting LUT sector (0x2E000 - 0x2F000):")
    # Print first 256 bytes
    for i in range(0, 128, 16):
        row = lut_chunk[i:i+16]
        print(f"  0x{0x2E000 + i:06X}: {row.hex(' ')}")

    # Check non-0xFF length in this block
    non_ff = sum(1 for b in lut_chunk if b != 0xFF)
    print(f"[+] Total LUT payload size: {non_ff} bytes in 4KB sector")

def main():
    analyze_gpio_configurations()
    analyze_eink_lut()

if __name__ == "__main__":
    main()
