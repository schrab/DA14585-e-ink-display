import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000

# 0x07FC2ED8: pc = 0x07FC2ED8 + 4 = 0x07FC2EDC + 0x194 = 0x07FC3070
off = 0x07FC3070 - base
val = struct.unpack_from("<I", data, off)[0]
print(f"Table pointer in GPIO_SetActive at 0x07FC3070: 0x{val:08X}")
