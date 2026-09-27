import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    fw = f.read()

base = 0x07FC0000

target = 0x07FCDA08

print(f"Search for references to 0x{target:08X}:")
for i in range(0, len(fw) - 4, 2):
    val = struct.unpack_from("<I", fw, i)[0]
    if val == target:
        addr = base + i
        print(f"Found reference to 0x{target:08X} at literal pool 0x{addr:08X}")
