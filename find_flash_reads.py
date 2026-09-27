import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

TARGET_READ = 0x07FC9774

offset = 0
instructions = []

while offset < len(data):
    chunk = data[offset : offset + 1024]
    disasms = list(md.disasm(chunk, base + offset))
    if disasms:
        instructions.extend(disasms)
        last_ins = disasms[-1]
        consumed = (last_ins.address + last_ins.size) - (base + offset)
        offset += consumed
    else:
        offset += 2

call_indices = []
for i, ins in enumerate(instructions):
    if ins.mnemonic in ('bl', 'b'):
        try:
            target = int(ins.op_str.lstrip('#'), 16)
            if target == TARGET_READ:
                call_indices.append(i)
        except ValueError:
            pass

print(f"\n[+] Found {len(call_indices)} calls to spi_flash_read_data (0x{TARGET_READ:08X}):")
for idx in call_indices:
    ins = instructions[idx]
    preceding = instructions[max(0, idx - 12) : idx + 1]
    print(f"\n--- Call at 0x{ins.address:08X} ---")
    for p in preceding:
        print(f"  0x{p.address:08X}: {p.mnemonic:8s} {p.op_str}")
