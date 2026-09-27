import struct

with open("da14585_full_ram_96k.bin", "rb") as f:
    ram = f.read()

def read32(addr):
    offset = addr - 0x07FC0000
    return struct.unpack("<I", ram[offset:offset+4])[0]

# pc for 0x07FC8950 is 0x07FC8954
p0 = read32(0x07FC8954 + 0x378)
p1 = read32(0x07FC8954 + 0x37c)

print(f"p0: 0x{p0:08X}")
print(f"p1: 0x{p1:08X}")
