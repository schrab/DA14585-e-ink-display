import struct
import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# In inspect_table_d8f0.py:
# 0x07FCD91C: 0x07FCD435 (Char 1 UUID: Command/Control)
# 0x07FCD96C: 0x07FCD445 (Char 2 UUID: Image Data Stream)
# Let's see the attribute table at 0x07FCD8F0 - 0x07FCD9B0
# And the message handler table at 0x07FCD9B0:
# 0x07FCD9B0: msg_id 0x0C13 -> 0x07FC704D
# 0x07FCD9B8: msg_id 0x0C15 -> 0x07FC7155
# 0x07FCD9C0: msg_id 0x0C17 -> 0x07FC6F09
# 0x07FCD9C8: msg_id 0x0C00 -> 0x07FC6F55
# 0x07FCD9D0: msg_id 0xFD06 -> 0x07FC4A93
# 0x07FCD9D8: msg_id 0xFD03 -> 0x07FC4AFB
# 0x07FCD9E0: msg_id 0xFD08 -> 0x07FC4A2B
# 0x07FCD9E8: msg_id 0xFD0E -> 0x07FC4509
# 0x07FCD9F0: msg_id 0xFD05 -> 0x07FC4B25

# Let's also check references to framebuffer 0x07FCF908 across all code!
print("=" * 70)
print("REFERENCES TO FRAMEBUFFER 0x07FCF908")
print("=" * 70)
for i in range(0, len(data) - 4, 2):
    val = struct.unpack_from("<I", data, i)[0]
    if val == 0x07FCF908:
        addr = base + i
        print(f"Found reference to FB 0x07FCF908 at literal 0x{addr:08X}")
