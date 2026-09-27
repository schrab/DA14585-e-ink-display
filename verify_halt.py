import keystone
import capstone
from test_eink_hardware import DRIVER_ASM

ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_THUMB)
encoding, _ = ks.asm(DRIVER_ASM, 0x07FD0000)
stub = bytes(encoding)

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
print(f"Stub size: {len(stub)} bytes")
for ins in md.disasm(stub, 0x07FD0000):
    if ins.address >= 0x07FD0130:
        hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
        print(f"  0x{ins.address:08X}: {hex_str:12s} {ins.mnemonic:8s} {ins.op_str}")
