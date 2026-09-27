#!/usr/bin/env python3
"""
DA14585 Image Header Generator (mkimage.py)
===========================================
Generates standard 64-byte Dialog Semiconductor multi-image application headers (s_imageHeader)
for DA14585 / DA14586 BLE SoCs. Compatible with Dialog Boot ROM and Secondary Bootloader.
"""

import sys
import os
import time
import zlib
import struct
import argparse

def generate_image_header(code_bytes, image_id=3, version="6.0.24.1464", timestamp=None):
    """Generate 64-byte Dialog s_imageHeader struct."""
    if timestamp is None:
        timestamp = int(time.time())

    sig = b'pQ'           # 0x70 0x51
    validflag = 0xAA      # STATUS_VALID_IMAGE
    code_size = len(code_bytes)
    crc = zlib.crc32(code_bytes)

    # 16-byte version string (null-terminated and padded with 0xFF)
    ver_bytes = version.encode('ascii')[:15] + b'\x00'
    ver_padded = ver_bytes + b'\xFF' * (16 - len(ver_bytes))

    flags = 0
    enc_pad = 0
    key_info = b'\xFF' * 6
    reserved = b'\xFF' * 24

    hdr = struct.pack('<2sBBII16sIBB6s24s',
                      sig, validflag, image_id, code_size, crc,
                      ver_padded, timestamp, flags, enc_pad, key_info, reserved)
    assert len(hdr) == 64, f"Header size must be 64 bytes, got {len(hdr)}"
    return hdr

def main():
    parser = argparse.ArgumentParser(description="DA14585 Image Header Generator")
    parser.add_argument("input_bin", help="Input raw application binary (.bin)")
    parser.add_argument("output_img", help="Output packaged firmware image (.img)")
    parser.add_argument("--id", type=int, default=3, help="Image ID (default: 3, to supersede Image 2 id=2)")
    parser.add_argument("--version", default="6.0.24.1464", help="Firmware version string")

    args = parser.parse_args()

    if not os.path.exists(args.input_bin):
        print(f"[-] Error: Input file '{args.input_bin}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(args.input_bin, "rb") as f:
        code_bytes = f.read()

    hdr = generate_image_header(code_bytes, image_id=args.id, version=args.version)
    packaged_img = hdr + code_bytes

    with open(args.output_img, "wb") as f:
        f.write(packaged_img)

    crc = zlib.crc32(code_bytes)
    print(f"[+] Packaged {len(code_bytes)} bytes into '{args.output_img}':")
    print(f"    - Image ID  : {args.id}")
    print(f"    - Version   : {args.version}")
    print(f"    - CRC32     : 0x{crc:08X}")
    print(f"    - Total Size: {len(packaged_img)} bytes (64-byte header + binary)")

if __name__ == "__main__":
    main()
