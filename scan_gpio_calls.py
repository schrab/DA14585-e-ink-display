import struct
import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

TARGET_SET = 0x07FC2EC0
TARGET_CLR = 0x07FC2F00
TARGET_CFG = 0x07FC2E2C

print("Scanning BL / BLX calls...")

def decode_bl(w1, w2, pc):
    # Cortex-M0 BL
    # w1: 11110 S imm10
    # w2: 11 J1 1 J2 imm11
    if (w1 & 0xF800) == 0xF000 and (w2 & 0xD800) == 0xD000:
        s = (w1 >> 10) & 1
        imm10 = w1 & 0x3FF
        j1 = (w2 >> 13) & 1
        j2 = (w2 >> 11) & 1
        imm11 = w2 & 0x7FF
        # ARMv6-M: J1 and J2 are NOT inverted with S if it's pure ARMv6-M,
        # but in standard Thumb-2 / ARMv6-M BL:
        # In ARMv6-M, bits 13 and 11 of w2 are both 1.
        # Let's compute offset:
        i1 = not (j1 ^ s)
        i2 = not (j2 ^ s)
        imm25 = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if imm25 & (1 << 24):
            imm25 -= (1 << 25)
        return pc + imm25
    return None

calls_set = []
calls_clr = []
calls_cfg = []

for offset in range(0, len(data) - 4, 2):
    w1, w2 = struct.unpack_from("<HH", data, offset)
    pc = base + offset + 4
    dest = decode_bl(w1, w2, pc)
    if dest == TARGET_SET:
        calls_set.append(pc - 4)
    elif dest == TARGET_CLR:
        calls_clr.append(pc - 4)
    elif dest == TARGET_CFG:
        calls_cfg.append(pc - 4)

print(f"Calls to GPIO_SetActive (0x{TARGET_SET:08X}): {len(calls_set)}")
print(f"Calls to GPIO_SetInactive (0x{TARGET_CLR:08X}): {len(calls_clr)}")
print(f"Calls to GPIO_ConfigurePin (0x{TARGET_CFG:08X}): {len(calls_cfg)}")

def print_caller_context(call_pc, name):
    call_offset = call_pc - base
    start_offset = max(0, call_offset - 20)
    chunk = data[start_offset : call_offset + 4]
    chunk_base = base + start_offset
    print(f"\n--- {name} at 0x{call_pc:08X} ---")
    for ins in md.disasm(chunk, chunk_base):
        print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

for c in calls_set[:15]:
    print_caller_context(c, "GPIO_SetActive")

for c in calls_clr[:15]:
    print_caller_context(c, "GPIO_SetInactive")
