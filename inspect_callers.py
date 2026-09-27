import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

def disasm_block(start_addr, end_addr, title):
    print(f"\n{'='*25} {title} (0x{start_addr:08X} - 0x{end_addr:08X}) {'='*25}")
    offset = start_addr - base
    length = end_addr - start_addr
    chunk = data[offset : offset + length]
    for ins in md.disasm(chunk, start_addr):
        hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
        print(f"  0x{ins.address:08X}: {hex_str:12s} {ins.mnemonic:8s} {ins.op_str}")

disasm_block(0x07FC3240, 0x07FC32B0, "Flash Read Caller 1")
disasm_block(0x07FC5310, 0x07FC5360, "Flash Read Caller 2")
disasm_block(0x07FC9C50, 0x07FC9D00, "Flash Read Caller 3")
disasm_block(0x07FC9D50, 0x07FC9D70, "Literals around 0x07FC9D58")
