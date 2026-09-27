"""
DA14585 E-Ink BLE Image Upload & Control Client
===============================================
Wirelessly connects to the DA14585 smart display over Bluetooth Low Energy (BLE)
and pushes custom images to the 4.2-inch (400x300) electronic paper display.

Service UUID:        afdbecdd-1234-abcd-2007-aabbccddeeff
Command Char UUID:   9e1547ba-c365-57b5-2947-c5e1c1e1d528 (Write, Notify)
Image Data UUID:     772ae377-b3d2-4f8e-4042-5481d121199c (Write Without Response)
"""

import sys
import os
import time
import asyncio
import argparse
from PIL import Image
from bleak import BleakScanner, BleakClient

# GATT UUID Definitions (RFC4122)
SERVICE_UUID        = "afdbecdd-1234-abcd-2007-aabbccddeeff"
CHAR_CMD_UUID       = "9e1547ba-c365-57b5-2947-c5e1c1e1d528"
CHAR_IMAGE_UUID     = "772ae377-b3d2-4f8e-4042-5481d121199c"

WIDTH  = 400
HEIGHT = 300
FRAME_SIZE = (WIDTH * HEIGHT) // 8  # 15,000 bytes
CHUNK_SIZE = 240                    # Max packet size below 247 MTU limit


def convert_image_to_bitmap(img_path: str) -> bytes:
    """Load an image file and convert to 15,000-byte 1-bit monochrome buffer."""
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"Image file not found: {img_path}")

    img = Image.open(img_path)
    # Resize and fit to 400x300
    img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    # Convert to 1-bit monochrome with Floyd-Steinberg dithering
    img = img.convert("1")

    # Pack into MSB-first scanlines
    raw_bytes = bytearray()
    for y in range(HEIGHT):
        for x_byte in range(WIDTH // 8):
            byte_val = 0
            for b in range(8):
                px = img.getpixel((x_byte * 8 + b, y))
                if px != 0:
                    byte_val |= (1 << (7 - b))
            raw_bytes.append(byte_val)

    assert len(raw_bytes) == FRAME_SIZE, f"Unexpected buffer size: {len(raw_bytes)}"
    return bytes(raw_bytes)


async def send_image_to_display(device_address: str, image_data: bytes):
    """Connect to the device and upload image frames."""
    print("=" * 70)
    print(f"Connecting to E-Ink Display: {device_address}...")
    print("=" * 70)

    async with BleakClient(device_address) as client:
        print(f"[+] Connected! MTU: {client.mtu_size}")

        # Check services
        services = client.services
        target_service = services.get_service(SERVICE_UUID)
        if not target_service:
            print(f"[-] Warning: Custom Service {SERVICE_UUID} not found directly in GATT table.")
            print("    Available services:")
            for s in services:
                print(f"      - {s.uuid} ({s.description})")

        # 1. Send Image Transfer Header / Start Command to Char 1
        print("[*] Initiating image transfer command...")
        # Framing: [0x06, length=0x02, mode=0x00, color=0x00]
        init_cmd = bytearray([0x06, 0x02, 0x00, 0x00])
        try:
            await client.write_gatt_char(CHAR_CMD_UUID, init_cmd, response=True)
            print("[+] Command acknowledged by display board.")
        except Exception as e:
            print(f"[!] Info: Command write returned: {e}")

        # 2. Stream 15,000 bytes in chunks of CHUNK_SIZE to Char 2
        total_chunks = (len(image_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
        print(f"[*] Streaming {len(image_data)} bytes in {total_chunks} chunks ({CHUNK_SIZE} B/chunk)...")
        t0 = time.time()

        for idx in range(total_chunks):
            offset = idx * CHUNK_SIZE
            chunk = image_data[offset : offset + CHUNK_SIZE]
            await client.write_gatt_char(CHAR_IMAGE_UUID, chunk, response=False)
            await asyncio.sleep(0.015)  # Yield to maintain BLE connection interval
            print(f"\r    Progress: {idx + 1}/{total_chunks} ({(idx + 1)/total_chunks*100:.1f}%)", end="")

        t1 = time.time()
        print(f"\n[+] Stream completed in {t1 - t0:.2f}s ({(len(image_data)/(t1-t0)/1024):.1f} KB/s)")

        # 3. Trigger Screen Refresh via Command Characteristic
        print("[*] Sending screen refresh trigger command...")
        refresh_cmd = bytearray([0x08, 0x01, 0x01])
        try:
            await client.write_gatt_char(CHAR_CMD_UUID, refresh_cmd, response=True)
            print("[+] Refresh trigger received! The display is now refreshing.")
        except Exception as e:
            print(f"[!] Info: Refresh command write returned: {e}")


async def discover_eink_device() -> str:
    """Scan and discover the E-Ink display MAC address."""
    print("[*] Scanning for E-Ink device (Local name: 'EINK-V115-42000')...")
    scanner = BleakScanner()
    devices = await scanner.discover(timeout=8.0, return_adv=True)

    for addr, (dev, adv) in devices.items():
        name = adv.local_name or dev.name or ""
        if "eink" in name.lower() or "420" in name.lower() or "11:e9:8f:9e:2a:86" in addr.lower():
            print(f"[+] Found Target Device: [{addr}] {name} (RSSI: {adv.rssi} dBm)")
            return addr

    return None


async def main():
    parser = argparse.ArgumentParser(description="DA14585 E-Ink BLE Image Transmitter")
    parser.add_argument("--image", "-i", default="test_pattern_400x300.png", help="Path to input image (PNG/JPG)")
    parser.add_argument("--device", "-d", default=None, help="Device BLE MAC address (auto-scans if omitted)")
    args = parser.parse_args()

    # Prepare bitmap
    bitmap = convert_image_to_bitmap(args.image)
    print(f"[+] Converted {args.image} to 400x300 1-bit bitmap ({len(bitmap)} bytes)")

    # Find device
    target_mac = args.device
    if not target_mac:
        target_mac = await discover_eink_device()

    if not target_mac:
        print("[-] Error: E-Ink display board not detected. Please verify power and advertising state.")
        print("    You can also specify the MAC directly with: python ble_eink_client.py --device <MAC>")
        sys.exit(1)

    # Upload
    await send_image_to_display(target_mac, bitmap)


if __name__ == "__main__":
    asyncio.run(main())
