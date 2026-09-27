import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

start_addr = 0x07FC28A0
end_addr   = 0x07FC2E2C

offset = start_addr - base
length = end_addr - start_addr
chunk = data[offset : offset + length]

print(f"Disassembling E-Ink Driver: 0x{start_addr:08X} - 0x{end_addr:08X} ({length} bytes)")
print("=" * 80)

for ins in md.disasm(chunk, start_addr):
    hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
    print(f"0x{ins.address:08X}: {hex_str:12s} {ins.mnemonic:8s} {ins.op_str}")
