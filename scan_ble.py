import asyncio
from bleak import BleakScanner

async def main():
    print("=" * 60)
    print("Scanning for Bluetooth LE devices (5 seconds)...")
    print("=" * 60)
    try:
        discovered = await BleakScanner.discover(timeout=5.0, return_adv=True)
        print(f"Discovered {len(discovered)} BLE devices:\n")
        for addr, (dev, adv) in discovered.items():
            name = adv.local_name or dev.name or "<Unknown>"
            print(f"  [{dev.address}] {name} (RSSI: {adv.rssi} dBm)")
            if adv.service_uuids:
                print(f"    Services: {adv.service_uuids}")
            if adv.manufacturer_data:
                mfg = {k: v.hex() for k, v in adv.manufacturer_data.items()}
                print(f"    Manufacturer Data: {mfg}")
            if "eink" in name.lower() or "420" in name.lower() or "11:e9" in dev.address.lower():
                print(f"    *** TARGET E-INK DISPLAY FOUND! ***")
    except Exception as e:
        print(f"Scan failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
