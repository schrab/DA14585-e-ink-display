import keystone

ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_THUMB)

ASM_CODE = """
.syntax unified
.thumb

// Test small stub
ldr r0, =0x50003002
movs r1, #1
strh r1, [r0]
bkpt #0
"""

encoding, count = ks.asm(ASM_CODE)
print(f"Assembled {count} instructions: {bytes(encoding).hex(' ')}")
