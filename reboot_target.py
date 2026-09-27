import time
from pyocd.core.helpers import ConnectHelper

print("Connecting to target to trigger System Reset (AIRCR.SYSRESETREQ)...")
probes = ConnectHelper.get_all_connected_probes()
probe = probes[0]
session = ConnectHelper.session_with_chosen_probe(
    unique_id=probe.unique_id,
    target_override="cortex_m",
    connect_mode="attach"
)
session.open()
target = session.target

AIRCR = 0xE000ED0C
# VECTKEY = 0x05FA0000, SYSRESETREQ = 0x00000004
print("[*] Triggering software SYSRESETREQ (0x05FA0004)...")
try:
    target.write32(AIRCR, 0x05FA0004)
except Exception as e:
    print(f"Write returned: {e} (expected during reset)")

session.close()
print("[+] Target reset issued. Microcontroller should now boot firmware from SPI flash!")
