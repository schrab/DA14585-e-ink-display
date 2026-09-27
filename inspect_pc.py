import capstone

with open('da14585_full_ram_96k.bin', 'rb') as f:
    ram = f.read()

base = 0x07FC0000

# Let's inspect 0x07FD68A0 and 0x07FD6740
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

for addr in (0x07FD6730, 0x07FD68A0):
    offset = addr - base
    chunk = ram[offset : offset + 32]
    print(f"\nDisassembly at 0x{addr:08X}:")
    for ins in md.disasm(chunk, addr):
        hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
        print(f"  0x{ins.address:08X}: {hex_str:12s} {ins.mnemonic:8s} {ins.op_str}")
