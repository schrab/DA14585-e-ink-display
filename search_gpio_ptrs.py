import struct
import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000

print("=== Search for references to GPIO_ConfigurePin (0x07FC2E2C / 0x07FC2E2D) ===")
for i in range(0, len(data) - 4, 2):
    val = struct.unpack_from("<I", data, i)[0]
    if val in (0x07FC2E2C, 0x07FC2E2D):
        addr = base + i
        print(f"Found pointer to GPIO_ConfigurePin at 0x{addr:08X}")

print("\n=== Search for references to GPIO_SetActive (0x07FC2EC0 / 0x07FC2EC1) ===")
for i in range(0, len(data) - 4, 2):
    val = struct.unpack_from("<I", data, i)[0]
    if val in (0x07FC2EC0, 0x07FC2EC1):
        addr = base + i
        print(f"Found pointer to GPIO_SetActive at 0x{addr:08X}")

print("\n=== Search for references to GPIO_SetInactive (0x07FC2F00 / 0x07FC2F01) ===")
for i in range(0, len(data) - 4, 2):
    val = struct.unpack_from("<I", data, i)[0]
    if val in (0x07FC2F00, 0x07FC2F01):
        addr = base + i
        print(f"Found pointer to GPIO_SetInactive at 0x{addr:08X}")
