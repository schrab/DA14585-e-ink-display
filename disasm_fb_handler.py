import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

addr = 0x07FC4350
offset = addr - base
chunk = data[offset : offset + 200]
print(f"Disassembling around 0x{addr:08X}:")
for ins in md.disasm(chunk, addr):
    hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
    print(f"  0x{ins.address:08X}: {hex_str:12s} {ins.mnemonic:8s} {ins.op_str}")
