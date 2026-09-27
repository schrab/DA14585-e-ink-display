import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000

print("=== Search for flash addresses around 0x2E000 in firmware ===")
for i in range(0, len(data) - 4, 2):
    val = struct.unpack_from("<I", data, i)[0]
    if 0x2D000 <= val <= 0x30000:
        addr = base + i
        print(f"0x{addr:08X} (offset 0x{i:04X}): 0x{val:08X}")
