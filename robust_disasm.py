import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

offset = 0
total_ins = 0
valid_ins = []

while offset < len(data):
    # Try disassembling
    chunk = data[offset : offset + 1024]
    disasms = list(md.disasm(chunk, base + offset))
    if disasms:
        valid_ins.extend(disasms)
        last_ins = disasms[-1]
        consumed = (last_ins.address + last_ins.size) - (base + offset)
        offset += consumed
    else:
        # Skip 2 bytes of data / unaligned
        offset += 2

print(f"Total instructions disassembled: {len(valid_ins)}")
