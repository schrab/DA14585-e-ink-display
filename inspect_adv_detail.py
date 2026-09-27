with open('da14585_full_ram_96k.bin', 'rb') as f:
    ram = f.read()

base = 0x07FC0000

# 0x07FD4C40
off = 0x07FD4C40 - base
print("RAM at 0x07FD4C30 - 0x07FD4C80:")
chunk = ram[off - 16 : off + 64]
print("Hex  :", chunk.hex(' '))
print("ASCII:", ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk))
