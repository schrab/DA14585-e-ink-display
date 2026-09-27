import time
from pyocd.core.helpers import ConnectHelper

probes = ConnectHelper.get_all_connected_probes()
probe = probes[0]
session = ConnectHelper.session_with_chosen_probe(
    unique_id=probe.unique_id,
    target_override="cortex_m",
    connect_mode="attach"
)
session.open()
target = session.target

target.halt()
target.write16(0x50003300, 0x0008)

# Test 1: Power OFF
target.write16(0x50003044, 0x08)  # P2_3 = 0
time.sleep(0.1)
p2_off = target.read16(0x50003040)
print(f"Power OFF: P2_DATA_REG = 0x{p2_off:04X} (BUSY: {p2_off & 1})")

# Test 2: Power ON
target.write16(0x50003042, 0x08)  # P2_3 = 1
time.sleep(0.1)
p2_on = target.read16(0x50003040)
print(f"Power ON : P2_DATA_REG = 0x{p2_on:04X} (BUSY: {p2_on & 1})")

# Test 3: Reset LOW
target.write16(0x50003004, 0x80)  # P0_7 = 0
time.sleep(0.05)
p2_rst_low = target.read16(0x50003040)
print(f"RST LOW  : P2_DATA_REG = 0x{p2_rst_low:04X} (BUSY: {p2_rst_low & 1})")

# Test 4: Reset HIGH
target.write16(0x50003002, 0x80)  # P0_7 = 1
time.sleep(0.05)
p2_rst_high = target.read16(0x50003040)
print(f"RST HIGH : P2_DATA_REG = 0x{p2_rst_high:04X} (BUSY: {p2_rst_high & 1})")

session.close()
