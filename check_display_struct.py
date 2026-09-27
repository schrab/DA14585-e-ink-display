import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000

# 0x07FC2B86: pc = 0x07FC2B86 + 4 = 0x07FC2B8A -> & ~3 = 0x07FC2B88 + 0x26c = 0x07FC2DF4
off = 0x07FC2DF4 - base
val = struct.unpack_from("<I", data, off)[0]
print(f"Display struct pointer at 0x07FC2DF4: 0x{val:08X}")
