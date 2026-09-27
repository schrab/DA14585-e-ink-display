import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000

# 0x07FC28F8: pc=0x07FC28F8 + 4 = 0x07FC28FC + 0x3b8 = 0x07FC2CB4
# 0x07FC2924: pc=0x07FC2924 + 4 = 0x07FC2928 + 0x38c = 0x07FC2CB4
off1 = 0x07FC28FC + 0x3b8 - base
off2 = 0x07FC2928 + 0x38c - base

val1 = struct.unpack_from("<I", data, off1)[0]
val2 = struct.unpack_from("<I", data, off2)[0]

print(f"Framebuffer pointer at 0x{base+off1:08X}: 0x{val1:08X}")
print(f"Framebuffer pointer at 0x{base+off2:08X}: 0x{val2:08X}")
