import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

def disasm_around(addr, length=128):
    offset = addr - base - 64
    chunk = data[offset : offset + length]
    start = addr - 64
    print(f"\nDisassembly around 0x{addr:08X}:")
    for ins in md.disasm(chunk, start):
        hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
        print(f"  0x{ins.address:08X}: {hex_str:12s} {ins.mnemonic:8s} {ins.op_str}")

disasm_around(0x07FC8F48)
disasm_around(0x07FCA324)
