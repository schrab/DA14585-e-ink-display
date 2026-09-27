with open('da14585_full_ram_96k.bin', 'rb') as f:
    ram = f.read()

base = 0x07FC0000

# Let's search for 0x2800 (Primary Service) in 16-bit words across all RAM
print("Scanning RAM for Primary Services (0x2800)...")
import struct

services = []
for i in range(0, len(ram) - 16, 2):
    val = struct.unpack_from("<H", ram, i)[0]
    if val == 0x2800:
        addr = base + i
        # In Dialog SDK attm_desc:
        # Check surrounding bytes
        ctx = ram[max(0, i-8) : i+32]
        # Look for potential UUIDs after 0x2800
        # If it's an attribute, following or preceding bytes will have service UUID
        print(f"0x{addr:08X} (offset 0x{i:05X}): {ctx.hex(' ')}")
