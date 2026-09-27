import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    fw = f.read()

base = 0x07FC0000

off = 0x07FCDAC0 - base
print("Words at 0x07FCDAC0 - 0x07FCDBE0:")
for i in range(off, off + 256, 4):
    w = struct.unpack_from("<I", fw, i)[0]
    print(f"0x{base+i:08X}: 0x{w:08X}")
