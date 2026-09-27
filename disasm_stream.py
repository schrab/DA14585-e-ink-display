import capstone

with open("da14585_full_ram_96k.bin", "rb") as f:
    ram = f.read()

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

print("\n--- 0x07FC28DC - 0x07FC2950 ---")
for ins in md.disasm(ram[0x28DC:0x2950], 0x07FC28DC):
    hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
    print(f"0x{ins.address:08X}: {hex_str:10s} {ins.mnemonic:8s} {ins.op_str}")
