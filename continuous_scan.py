import asyncio
import time
from bleak import BleakScanner

async def main():
    print("=" * 70)
    print("Continuous BLE Scanner (20 seconds)...")
    print("Looking for EINK, 11:E9:8F:9E:2A:86, or DA14585 advertisements...")
    print("=" * 70)

    seen = set()

    def callback(device, advertisement_data):
        name = advertisement_data.local_name or device.name or "<Unknown>"
        mac = device.address.upper()
        # Filter duplicates unless it's an e-ink candidate
        is_target = "eink" in name.lower() or "420" in name.lower() or "11:E9" in mac or "CDAB" in str(advertisement_data.manufacturer_data)
        if mac not in seen or is_target:
            seen.add(mac)
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] [{mac}] {name} (RSSI: {advertisement_data.rssi} dBm)")
            if advertisement_data.service_uuids:
                print(f"       Services: {advertisement_data.service_uuids}")
            if advertisement_data.manufacturer_data:
                mfg = {f"0x{k:04X}": v.hex() for k, v in advertisement_data.manufacturer_data.items()}
                print(f"       Mfg Data: {mfg}")
            if is_target:
                print(f"       >>> TARGET E-INK BADGE DETECTED! <<<")

    scanner = BleakScanner(detection_callback=callback)
    await scanner.start()
    await asyncio.sleep(20.0)
    await scanner.stop()
    print("=" * 70)
    print(f"Scan complete. Total unique devices seen: {len(seen)}")

if __name__ == "__main__":
    asyncio.run(main())
