import time
from pyocd.core.helpers import ConnectHelper

RAM_BIN = "da14585_full_ram_96k.bin"
RAM_BASE = 0x07FC0000

with open(RAM_BIN, "rb") as f:
    ram_data = f.read()

print(f"Restoring entire 96 KB live RAM image ({len(ram_data)} bytes)...")

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

t0 = time.time()
target.write_memory_block8(RAM_BASE, list(ram_data))
t1 = time.time()
print(f"[+] Restored 96 KB in {t1 - t0:.2f} seconds ({len(ram_data)/(t1-t0)/1024:.1f} KB/s)")

# Ensure Remap to SysRAM
sys_ctrl = target.read16(0x50000012)
sys_ctrl = (sys_ctrl & ~0x3) | 0x3
target.write16(0x50000012, sys_ctrl)

# Set vector table registers from pristine dump
sp = 0x07FD392C
pc = 0x07FC8B3C
lr = 0x07F1B755

# Or reset from Reset Vector
reset_sp = target.read32(RAM_BASE)
reset_pc = target.read32(RAM_BASE + 4)
print(f"[+] Reset Vector: SP=0x{reset_sp:08X}, PC=0x{reset_pc:08X}")

target.write_core_register("sp", reset_sp)
target.write_core_register("pc", reset_pc)
target.write_core_register("lr", 0xFFFFFFFF)
target.write_core_register("xpsr", 0x01000000)

# Unfreeze watchdog
target.write16(0x50003302, 0x0008)

print("[*] Resuming target execution from pristine application image...")
target.resume()
session.close()
print("[+] Target resumed.")
