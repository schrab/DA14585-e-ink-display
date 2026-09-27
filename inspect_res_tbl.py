import struct

with open('da14585_full_ram_96k.bin', 'rb') as f:
    ram = f.read()

base = 0x07FC0000
off = 0x07FD4BB8 - base

print("Dump of 0x07FD4BB8 in full RAM image:")
for i in range(off, off + 96, 4):
    w = struct.unpack_from("<I", ram, i)[0]
    print(f"0x{base+i:08X}: 0x{w:08X}")
