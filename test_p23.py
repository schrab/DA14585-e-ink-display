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

print("Writing 0x08 (P2_3 PWR_EN) to P2_SET_DATA_REG (0x50003042)...")
target.write16(0x50003042, 0x08)
p2 = target.read16(0x50003040)
print(f"P2_DATA_REG after SET: 0x{p2:04X} (P2_3: {(p2 >> 3) & 1})")

print("Writing 0x08 to P2_RESET_DATA_REG (0x50003044)...")
target.write16(0x50003044, 0x08)
p2 = target.read16(0x50003040)
print(f"P2_DATA_REG after RESET: 0x{p2:04X} (P2_3: {(p2 >> 3) & 1})")

session.close()
