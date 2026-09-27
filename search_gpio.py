import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000

print("=== Peripheral Literals (0x5000_0000 - 0x5000_4000) ===")
for i in range(0, len(data) - 4, 2):
    val = struct.unpack_from("<I", data, i)[0]
    if 0x50000000 <= val <= 0x50004000:
        addr = base + i
        print(f"0x{addr:08X} (offset 0x{i:04X}): 0x{val:08X}")
