with open("da14585_nvds_calib.bin", "rb") as f:
    data = f.read()

print(f"NVDS Data ({len(data)} bytes):")
print("Hex   :", data.hex(" "))
print("ASCII :", ''.join(chr(b) if 32 <= b < 127 else '.' for b in data))
