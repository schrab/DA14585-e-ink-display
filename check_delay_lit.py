import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000

off = 0x07FC29F4 - base
val = struct.unpack_from("<I", data, off)[0]
print(f"Delay literal at 0x07FC29F4: 0x{val:08X}")
