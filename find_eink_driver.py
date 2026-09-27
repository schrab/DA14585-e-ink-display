import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

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

ins_by_addr = {ins.address: ins for ins in instructions}

print(f"Total instructions: {len(instructions)}")

TARGETS = {
    0x07FC2EC0: "GPIO_SetActive",
    0x07FC2F00: "GPIO_SetInactive",
    0x07FC2E2C: "GPIO_ConfigurePin",
}

# Group calls by target
calls = {t: [] for t in TARGETS}

for i, ins in enumerate(instructions):
    if ins.mnemonic in ('bl', 'b'):
        try:
            target = int(ins.op_str.lstrip('#'), 16)
            if target in TARGETS:
                calls[target].append(i)
        except ValueError:
            pass

print("\n" + "="*70)
print("CALLS TO GPIO FUNCTIONS")
print("="*70)

for target, name in TARGETS.items():
    call_indices = calls[target]
    print(f"\n[+] {name} (0x{target:08X}) called {len(call_indices)} times:")
    for idx in call_indices:
        ins = instructions[idx]
        # Show preceding 6 instructions to see arguments (r0=port, r1=pin)
        preceding = instructions[max(0, idx - 6) : idx + 1]
        context_str = " | ".join(f"{p.mnemonic} {p.op_str}" for p in preceding[:-1])
        print(f"  0x{ins.address:08X}: [{context_str}] -> {ins.mnemonic} {ins.op_str}")

