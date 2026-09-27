import capstone

with open('da14585_full_ram_96k.bin', 'rb') as f:
    ram = f.read()

base = 0x07FC0000
addr = 0x07FD67EE
offset = addr - base

chunk = ram[offset : offset + 32]
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
print(f"Code at 0x{addr:08X}:")
for ins in md.disasm(chunk, addr):
    hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
    print(f"  0x{ins.address:08X}: {hex_str:12s} {ins.mnemonic:8s} {ins.op_str}")
