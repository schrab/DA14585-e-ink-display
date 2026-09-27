import time
from pyocd.core.helpers import ConnectHelper

FW_BIN = "da14585_fw_image1.bin"
FW_BASE = 0x07FC0000

with open(FW_BIN, "rb") as f:
    fw_data = f.read()

print(f"Loading {len(fw_data)} bytes of {FW_BIN} into SysRAM (0x{FW_BASE:08X})...")

probes = ConnectHelper.get_all_connected_probes()
probe = probes[0]
session = ConnectHelper.session_with_chosen_probe(
    unique_id=probe.unique_id,
    target_override="cortex_m",
    frequency=1000000,
    connect_mode="attach"
)
session.open()
target = session.target

target.halt()
# Freeze watchdog
target.write16(0x50003300, 0x0008)

# Write firmware image to SysRAM
t0 = time.time()
target.write_memory_block8(FW_BASE, list(fw_data))
t1 = time.time()
print(f"[+] Written {len(fw_data)} bytes in {t1 - t0:.2f} seconds ({len(fw_data)/(t1-t0)/1024:.1f} KB/s)")

# Set REMAP_ADR0 to SysRAM (0x3) so 0x00000000 maps to 0x07FC0000
sys_ctrl = target.read16(0x50000012)
sys_ctrl = (sys_ctrl & ~0x3) | 0x3
target.write16(0x50000012, sys_ctrl)

# Read vector table from SysRAM base
sp = target.read32(FW_BASE)
reset_vec = target.read32(FW_BASE + 4)
print(f"[+] Initial SP: 0x{sp:08X}, Reset Vector: 0x{reset_vec:08X}")

target.write_core_register("sp", sp)
target.write_core_register("pc", reset_vec)
target.write_core_register("lr", 0xFFFFFFFF)
target.write_core_register("xpsr", 0x01000000)  # Thumb bit

# Unfreeze watchdog before resuming so normal OS watchdog servicing works
target.write16(0x50003302, 0x0008)

print("[*] Resuming target execution from Reset Handler...")
target.resume()
session.close()
print("[+] Target is now running active firmware!")
