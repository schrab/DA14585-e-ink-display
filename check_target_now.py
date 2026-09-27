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
state = target.get_state().name
print(f"Target state: {state}")
if state != "HALTED":
    target.halt()

pc = target.read_core_register("pc")
sp = target.read_core_register("sp")
lr = target.read_core_register("lr")
flag = target.read32(0x07FD03FC)
p0 = target.read16(0x50003000)
p2 = target.read16(0x50003040)

print(f"PC: 0x{pc:08X} | SP: 0x{sp:08X} | LR: 0x{lr:08X}")
print(f"Flag at 0x07FD03FC: 0x{flag:08X}")
print(f"P0_DATA_REG: 0x{p0:04X} | P2_DATA_REG: 0x{p2:04X}")

session.close()
