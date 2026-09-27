import struct

with open('da14585_fw_image1.bin', 'rb') as f:
    fw_data = f.read()

with open('da14585_full_ram_96k.bin', 'rb') as f:
    ram_data = f.read()

print("=" * 70)
print("BLE ATT / GATT / ADVERTISING PROFILE ANALYSIS")
print("=" * 70)

# In Dialog SDK, Custom Service 1 attribute table contains:
# struct attm_desc_128 {
#     uint8_t uuid[16];
#     uint16_t perm;
#     uint16_t max_length;
#     ...
# }

# Let's search for strings in firmware
import re

strings = re.findall(b"[A-Za-z0-9_\\-\\.\t :]{4,}", fw_data)
print(f"[+] Found {len(strings)} ASCII strings in firmware:")
for s in strings:
    s_str = s.decode('ascii', errors='ignore')
    if any(k in s_str.lower() for k in ('eink', 'ble', 'cust', 'adv', 'gatt', 'serv', 'ota', 'dis', 'dev', 'name')):
        print(f"    '{s_str}'")

# Look in RAM dump for live BLE advertising data and names
ram_strings = re.findall(b"[A-Za-z0-9_\\-\\.\t :]{4,}", ram_data)
print(f"\n[+] Key strings in live RAM:")
for s in ram_strings:
    s_str = s.decode('ascii', errors='ignore')
    if any(k in s_str.lower() for k in ('eink', '420', 'v115', 'adv')):
        print(f"    '{s_str}'")
