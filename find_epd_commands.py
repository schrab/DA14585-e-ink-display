import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

TARGET_CMD = 0x07FC2A28
TARGET_DAT = 0x07FC2A50  # or 0x07FC2A54

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

cmd_calls = []
dat_calls = []

for i, ins in enumerate(instructions):
    if ins.mnemonic in ('bl', 'b'):
        try:
            target = int(ins.op_str.lstrip('#'), 16)
            if target == TARGET_CMD:
                cmd_calls.append(i)
            elif target in (0x07FC2A50, 0x07FC2A54):
                dat_calls.append(i)
        except ValueError:
            pass

print(f"[+] Total calls to epd_write_command (0x{TARGET_CMD:08X}): {len(cmd_calls)}")
for idx in cmd_calls:
    ins = instructions[idx]
    preceding = instructions[max(0, idx - 4) : idx + 1]
    context = " | ".join(f"{p.mnemonic} {p.op_str}" for p in preceding[:-1])
    print(f"  0x{ins.address:08X}: [{context}] -> {ins.mnemonic} {ins.op_str}")

print(f"\n[+] Total calls to epd_write_data (0x07FC2A54): {len(dat_calls)}")
for idx in dat_calls:
    ins = instructions[idx]
    preceding = instructions[max(0, idx - 4) : idx + 1]
    context = " | ".join(f"{p.mnemonic} {p.op_str}" for p in preceding[:-1])
    print(f"  0x{ins.address:08X}: [{context}] -> {ins.mnemonic} {ins.op_str}")

