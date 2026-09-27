import sys
from pyocd.core.helpers import ConnectHelper

probes = ConnectHelper.get_all_connected_probes()
if not probes:
    print("No ST-Link probe found.")
    sys.exit(0)

probe = probes[0]
session = ConnectHelper.session_with_chosen_probe(
    unique_id=probe.unique_id,
    target_override="cortex_m",
    connect_mode="attach"
)
session.open()
target = session.target
state = target.get_state().name
print(f"Target State: {state}")
session.close()
