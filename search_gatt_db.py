import struct
import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    fw = f.read()

base = 0x07FC0000

# Search for GATT Service Declarations:
# Primary Service Declaration UUID is 0x2800.
# Secondary Service Declaration UUID is 0x2801.
# Characteristic Declaration UUID is 0x2803.
# Client Characteristic Configuration Descriptor (CCCD) is 0x2902.

print("=== Search for 0x2800, 0x2803, 0x2902 in firmware ===")
for i in range(0, len(fw) - 2, 2):
    val = struct.unpack_from("<H", fw, i)[0]
    if val == 0x2800:
        addr = base + i
        # Check context
        ctx = fw[max(0, i-4) : i+32]
        print(f"0x{addr:08X} (Primary Service 0x2800): {ctx.hex(' ')}")
    elif val == 0x2902:
        addr = base + i
        ctx = fw[max(0, i-4) : i+20]
        print(f"0x{addr:08X} (CCCD 0x2902): {ctx.hex(' ')}")

