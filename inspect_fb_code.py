import capstone

with open('da14585_full_ram_96k.bin', 'rb') as f:
    ram = f.read()

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

def disasm_range(start, length):
    print(f"\n--- 0x{start:08X} ({length} bytes) ---")
    offset = start - 0x07FC0000
    for ins in md.disasm(ram[offset:offset+length], start):
        hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
        print(f"0x{ins.address:08X}: {hex_str:10s} {ins.mnemonic:8s} {ins.op_str}")

disasm_range(0x07FC43A0, 0x60)
disasm_range(0x07FC8CA0, 0x50)
disasm_range(0x07FC93E0, 0x50)
