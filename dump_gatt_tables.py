import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    fw = f.read()

base = 0x07FC0000

# 0x07FCDA00
start = 0x07FCD980 - base
end = 0x07FCE500 - base
chunk = fw[start:end]

print("=" * 80)
print(f"GATT ATTRIBUTE DATABASE DUMP (0x07FCD980 - 0x07FCE500)")
print("=" * 80)

for i in range(0, len(chunk), 16):
    addr = 0x07FCD980 + i
    row = chunk[i:i+16]
    hex_str = ' '.join(f'{b:02x}' for b in row)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)
    print(f"0x{addr:08X}: {hex_str:48s} | {ascii_str}")
