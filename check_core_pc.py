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
# Freeze watchdog
target.write16(0x50003300, 0x0008)

pc = target.read_core_register("pc")
sp = target.read_core_register("sp")
lr = target.read_core_register("lr")
print(f"Current State: HALTED | PC: 0x{pc:08X} | SP: 0x{sp:08X} | LR: 0x{lr:08X}")

# Unhalt and resume
target.resume()
session.close()
