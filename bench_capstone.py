import time
import capstone

t0 = time.time()
with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

instructions = list(md.disasm(data, base))
t1 = time.time()
print(f"Disassembled {len(instructions)} instructions in {t1 - t0:.2f} seconds!")
