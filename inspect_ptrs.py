import struct

with open("da14585_full_ram_96k.bin", "rb") as f:
    ram = f.read()

def read32(addr):
    offset = addr - 0x07FC0000
    return struct.unpack("<I", ram[offset:offset+4])[0]

# pc for 0x07FC28EA is (0x07FC28EA + 4) & ~3 = 0x07FC28EC
ptr_flag = read32(0x07FC28EC + 0x3c0)
ptr_red = read32(0x07FC28F8 + 4 + 0x3b8)
ptr_bw = read32(0x07FC2924 + 4 + 0x38c)

print(f"ptr_flag: 0x{ptr_flag:08X}")
print(f"ptr_red:  0x{ptr_red:08X}")
print(f"ptr_bw:   0x{ptr_bw:08X}")
