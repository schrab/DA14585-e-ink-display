"""
DA14585 E-Ink BLE Image Upload & Control Client
===============================================
Wirelessly connects to the DA14585 smart display over Bluetooth Low Energy (BLE)
and pushes custom monochrome or tri-color images to the 4.2-inch (400x300) electronic paper display.

Service UUID:        afdbecdd-1234-abcd-2007-aabbccddeeff
Command Char UUID:   9e1547ba-c365-57b5-2947-c5e1c1e1d528 (Write, Notify)
Image Data UUID:     772ae377-b3d2-4f8e-4042-5481d121199c (Write Without Response, Write)
"""

import sys
import os
import time
import asyncio
import argparse
from PIL import Image
from bleak import BleakScanner, BleakClient

# GATT UUID Definitions (RFC4122)
SERVICE_UUID    = "afdbecdd-1234-abcd-2007-aabbccddeeff"
CHAR_CMD_UUID   = "9e1547ba-c365-57b5-2947-c5e1c1e1d528"
CHAR_IMAGE_UUID = "772ae377-b3d2-4f8e-4042-5481d121199c"

WIDTH  = 400
HEIGHT = 300
PLANE_SIZE = (WIDTH * HEIGHT) // 8  # 15,000 bytes per color plane
TOTAL_FRAME_SIZE = PLANE_SIZE * 2   # 30,000 bytes (BW plane + Red plane)
MAX_CHUNK_PAYLOAD = 240             # + 2 bytes offset header = 242 bytes <= 247 MTU


def convert_image_to_tricolor_buffer(img_path: str) -> bytes:
    """Load an image file and convert to 30,000-byte dual-plane (BW + Red) buffer."""
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"Image file not found: {img_path}")

    img = Image.open(img_path).convert("RGB")
    img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

    bw_bytes = bytearray()
    red_bytes = bytearray()

    for y in range(HEIGHT):
        for x_byte in range(WIDTH // 8):
            bw_val = 0
            red_val = 0
            for b in range(8):
                px = img.getpixel((x_byte * 8 + b, y))
                # Detect color in RGB:
                # Red:   R is dominant over G and B
                # Black: All low luminance
                # White: All high luminance
                r, g, b_c = px[0], px[1], px[2]
                is_red = (r > 140 and g < 110 and b_c < 110)
                is_black = (r < 110 and g < 110 and b_c < 110)

                bit_pos = 7 - b

                # BW RAM (0x24): 1 = White/Red, 0 = Black
                if not is_black:
                    bw_val |= (1 << bit_pos)

                # RED RAM (0x26): 1 = Red, 0 = Non-Red
                if is_red:
                    red_val |= (1 << bit_pos)

            bw_bytes.append(bw_val)
            red_bytes.append(red_val)

    assert len(bw_bytes) == PLANE_SIZE, f"Unexpected BW size: {len(bw_bytes)}"
    assert len(red_bytes) == PLANE_SIZE, f"Unexpected Red size: {len(red_bytes)}"

    # Concatenate: [0..14999] = BW, [15000..29999] = Red
    return bytes(bw_bytes + red_bytes)


async def send_image_to_display(device_address: str, image_data: bytes):
    """Connect to the device and upload image frames."""
    print("=" * 70)
    print(f"Connecting to E-Ink Display: {device_address}...")
    print("=" * 70)

    async with BleakClient(device_address) as client:
        print(f"[+] Connected! MTU: {client.mtu_size}")

        # 1. Clear display buffer on device: Command 0x07
        print("[*] Sending buffer clear command (0x07)...")
        await client.write_gatt_char(CHAR_CMD_UUID, bytearray([0x07]), response=True)
        print("[+] Display buffer initialized.")

        # 2. Stream 30,000 bytes in offset-tagged chunks
        total_len = len(image_data)
        total_chunks = (total_len + MAX_CHUNK_PAYLOAD - 1) // MAX_CHUNK_PAYLOAD
        print(f"[*] Streaming {total_len} bytes in {total_chunks} packets (up to {MAX_CHUNK_PAYLOAD} B/pkt)...")
        t0 = time.time()

        for idx in range(total_chunks):
            offset = idx * MAX_CHUNK_PAYLOAD
            chunk = image_data[offset : offset + MAX_CHUNK_PAYLOAD]

            # Header: [offset_lo, offset_hi] + payload
            packet = bytearray([offset & 0xFF, (offset >> 8) & 0xFF]) + chunk
            await client.write_gatt_char(CHAR_IMAGE_UUID, packet, response=False)
            await asyncio.sleep(0.015)  # Yield to maintain BLE connection interval
            print(f"\r    Progress: {idx + 1}/{total_chunks} ({(idx + 1)/total_chunks*100:.1f}%)", end="")

        t1 = time.time()
        print(f"\n[+] Stream completed in {t1 - t0:.2f}s ({(total_len/(t1-t0)/1024):.1f} KB/s)")

        # 3. Trigger Screen Refresh via Command 0x06
        print("[*] Sending screen refresh trigger command (0x06)...")
        try:
            await client.write_gatt_char(CHAR_CMD_UUID, bytearray([0x06]), response=True)
            print("[+] Refresh trigger acknowledged! Display is now physically refreshing...")
        except Exception as e:
            # During refresh, CPU blocks for ~17s and BLE connection drops as expected
            print(f"[*] Note: Display refresh started (connection closed: {e})")


async def discover_eink_device() -> str:
    """Scan and discover the E-Ink display MAC address."""
    print("[*] Scanning for E-Ink device (Local name: 'EINK-V115-42000')...")
    scanner = BleakScanner()
    devices = await scanner.discover(timeout=8.0, return_adv=True)

    for addr, (dev, adv) in devices.items():
        name = adv.local_name or dev.name or ""
        if "eink" in name.lower() or "42000" in name.lower():
            print(f"[+] Found Target Device: [{addr}] {name} (RSSI: {adv.rssi} dBm)")
            return addr

    return None


async def main():
    parser = argparse.ArgumentParser(description="DA14585 E-Ink BLE Image Transmitter")
    parser.add_argument("--image", "-i", default="test_pattern_red_400x300.png", help="Path to input image (PNG/JPG)")
    parser.add_argument("--device", "-d", default=None, help="Device BLE MAC address (auto-scans if omitted)")
    args = parser.parse_args()

    # Convert image to dual-buffer 30,000-byte stream
    tricolor_data = convert_image_to_tricolor_buffer(args.image)
    print(f"[+] Converted {args.image} to 400x300 tri-color buffer ({len(tricolor_data)} bytes)")

    # Find device
    target_mac = args.device
    if not target_mac:
        target_mac = await discover_eink_device()

    if not target_mac:
        print("[-] Error: E-Ink display board not detected. Please verify power and advertising state.")
        sys.exit(1)

    # Upload and refresh
    await send_image_to_display(target_mac, tricolor_data)


if __name__ == "__main__":
    asyncio.run(main())
