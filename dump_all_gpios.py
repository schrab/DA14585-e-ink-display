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

print("=== PORT 0 REGISTERS ===")
print(f"P0_DATA_REG      : 0x{target.read16(0x50003000):04X}")
print(f"P00_MODE_REG(CLK): 0x{target.read16(0x50003006):04X}")
print(f"P05_MODE_REG(DC) : 0x{target.read16(0x50003010):04X}")
print(f"P06_MODE_REG(DIN): 0x{target.read16(0x50003012):04X}")
print(f"P07_MODE_REG(RST): 0x{target.read16(0x50003014):04X}")

print("\n=== PORT 2 REGISTERS ===")
print(f"P2_DATA_REG      : 0x{target.read16(0x50003040):04X}")
print(f"P20_MODE_REG(BSY): 0x{target.read16(0x50003046):04X}")
print(f"P21_MODE_REG(CS) : 0x{target.read16(0x50003048):04X}")
print(f"P23_MODE_REG(PWR): 0x{target.read16(0x5000304C):04X}")

session.close()
