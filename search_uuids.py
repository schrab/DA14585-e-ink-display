import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    fw = f.read()

base = 0x07FC0000

# Search for the function that creates the BLE custom service:
# In Dialog SDK, attmdb_add_service or attm_svc_create_db_128 is called.
# Let's search for any UUID128 array in the data section (0x07FCB000 - 0x07FCE000)

print("Scanning for UUIDs in firmware data section...")

# Let's check all arrays of 16 bytes in data section
for off in range(0, len(fw) - 16, 2):
    chunk = fw[off : off + 16]
    # Check if it has Bluetooth Base UUID or distinctive vendor UUID pattern
    if chunk[4:] == b"\x00\x00\x10\x00\x80\x00\x00\x80\x5f\x9b\x34\xfb" or \
       chunk[:12] == b"\xfb\x34\x9b\x5f\x80\x00\x00\x80\x00\x10\x00\x00":
        addr = base + off
        print(f"Standard Bluetooth UUID at 0x{addr:08X}: {chunk.hex()}")

# Also look for Dialog default SUOTA UUID or custom 128-bit service UUID
# Dialog SUOTA UUID: 0xFEF5 or 128-bit:
# 5A 87 B4 EF 3B 3A 11 E4 A8 14 00 02 A5 D5 C5 1B
for off in range(0, len(fw) - 16, 2):
    chunk = fw[off : off + 16]
    if b"\x5a\x87\xb4\xef" in chunk or b"\x1b\xc5\xd5\xa5" in chunk:
        addr = base + off
        print(f"Found Dialog SUOTA UUID at 0x{addr:08X}: {chunk.hex()}")

