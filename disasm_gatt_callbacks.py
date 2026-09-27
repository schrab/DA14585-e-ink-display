import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

def disasm_func(addr, length=128):
    offset = addr - base
    chunk = data[offset : offset + length]
    print(f"\nDisassembling at 0x{addr:08X}:")
    for ins in md.disasm(chunk, addr):
        hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
        print(f"  0x{ins.address:08X}: {hex_str:12s} {ins.mnemonic:8s} {ins.op_str}")

disasm_func(0x07FC4D74, 96)
disasm_func(0x07FC4E34, 96)
disasm_func(0x07FC4EFC, 96)
