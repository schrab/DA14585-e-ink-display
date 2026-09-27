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
p2 = target.read16(0x50003040)
print(f"Current P2_DATA_REG: 0x{p2:04X} (BUSY P2_0: {p2 & 1})")
session.close()
