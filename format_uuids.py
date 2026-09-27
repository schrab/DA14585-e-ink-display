with open('da14585_fw_image1.bin', 'rb') as f:
    fw = f.read()

base = 0x07FC0000

def print_uuid(name, addr):
    off = addr - base
    u = fw[off : off + 16]
    # Little-endian (wire order in BLE)
    wire = u.hex()
    # RFC4122 format (reversed)
    rfc = f"{u[15]:02x}{u[14]:02x}{u[13]:02x}{u[12]:02x}-{u[11]:02x}{u[10]:02x}-{u[9]:02x}{u[8]:02x}-{u[7]:02x}{u[6]:02x}-{u[5]:02x}{u[4]:02x}{u[3]:02x}{u[2]:02x}{u[1]:02x}{u[0]:02x}"
    print(f"{name} at 0x{addr:08X}:")
    print(f"  Raw Wire (Hex): {u.hex(' ')}")
    print(f"  RFC4122 Standard: {rfc}")

print("=" * 70)
print("EXTRACTED BLE GATT 128-BIT UUIDS")
print("=" * 70)
print_uuid("Service UUID", 0x07FCDA08)
print_uuid("Characteristic 1 (Command/Control, 20B)", 0x07FCD435)
print_uuid("Characteristic 2 (Image Data Stream, 247B)", 0x07FCD445)
