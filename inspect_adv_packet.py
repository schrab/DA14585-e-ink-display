import struct

with open('da14585_full_ram_96k.bin', 'rb') as f:
    ram = f.read()

base = 0x07FC0000

# Search for b'\x09EINK'
pos = 0
print("=== Advertising Packets in RAM ===")
while True:
    idx = ram.find(b"\x09EINK", pos)
    if idx == -1:
        break
    addr = base + idx
    # Print 32 bytes around this
    start = max(0, idx - 4)
    chunk = ram[start : start + 36]
    print(f"Address 0x{addr:08X} (offset 0x{idx:05X}):")
    print(f"  Hex  : {chunk.hex(' ')}")
    print(f"  ASCII: {''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)}")
    pos = idx + 1

