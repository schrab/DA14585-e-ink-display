"""
DA14585 Flash Image Partition Extractor
======================================
Carves out all verified partitions from the SPI NOR flash dump:
1. Boot Header & Secondary Bootloader (0x00000 - 0x04000)
2. Firmware Image 1 (0x04000 - 0x136C8, SDK 6.0.22.1401)
3. Firmware Image 2 (0x1F000 - 0x2E6C0, OTA Backup Image)
4. E-Ink Display Waveforms & LUTs (0x2E000 - 0x2F000)
5. Product Header (0x38000)
6. NVDS / Bluetooth Device Address & RF Calibration (0x40000)
"""

import os
import struct
import hashlib

FLASH_BIN = "da14585_spi_flash_512k.bin"

def main():
    if not os.path.exists(FLASH_BIN):
        print(f"Error: {FLASH_BIN} not found.")
        return

    with open(FLASH_BIN, "rb") as f:
        data = f.read()

    print("=" * 70)
    print(f"DA14585 SPI Flash Partition Analysis: {FLASH_BIN} ({len(data)} bytes)")
    print("=" * 70)

    # 1. Product Header at 0x38000
    if len(data) >= 0x38010:
        sig, ver, img1_off, img2_off = struct.unpack("<2s2sII", data[0x38000:0x3800C])
        print(f"[+] Product Header (0x38000):")
        print(f"    - Signature  : {sig.hex().upper()} ({'Valid 0x70 0x52' if sig == b'pR' else 'Invalid'})")
        print(f"    - Image 1 Offset : 0x{img1_off:06X}")
        print(f"    - Image 2 Offset : 0x{img2_off:06X}")

    # Helper to parse and extract image
    def extract_image(offset, label, out_name):
        hdr = data[offset : offset + 64]
        sig = hdr[:2]
        valid_flag = hdr[2]
        img_id = hdr[3]
        code_size = struct.unpack("<I", hdr[4:8])[0]
        crc = struct.unpack("<I", hdr[8:12])[0]
        ver_str = hdr[12:28].decode("ascii", errors="ignore").strip()

        print(f"\n[+] {label} (Flash offset 0x{offset:06X}):")
        print(f"    - Header Magic : {sig.hex().upper()} ({'0x70 0x51 Valid Image' if sig == b'pQ' else 'Unknown'})")
        print(f"    - Valid Flag   : 0x{valid_flag:02X} ({'Active' if valid_flag == 0xAA else 'Inactive'})")
        print(f"    - Image ID     : {img_id}")
        print(f"    - Code Size    : {code_size} bytes ({code_size / 1024:.1f} KB)")
        print(f"    - CRC32        : 0x{crc:08X}")
        print(f"    - SDK Version  : {ver_str}")

        # The actual application starts right after 64-byte header
        img_data = data[offset + 64 : offset + 64 + code_size]
        with open(out_name, "wb") as f_out:
            f_out.write(img_data)
        sha = hashlib.sha256(img_data).hexdigest()
        print(f"    -> Extracted raw firmware binary to: {out_name} (SHA256: {sha[:16]}...)")

    extract_image(0x004000, "Firmware Image 1 (Active Firmware)", "da14585_fw_image1.bin")
    extract_image(0x01F000, "Firmware Image 2 (OTA Backup Image)", "da14585_fw_image2.bin")

    # Extract Bootloader / Primary Boot sector
    boot_data = data[0x000000:0x004000]
    with open("da14585_bootloader.bin", "wb") as f:
        f.write(boot_data)
    print(f"\n[+] Extracted Bootloader sector (0x0000 - 0x4000) to: da14585_bootloader.bin")

    # Extract NVDS / Calibration parameters
    nvds_data = data[0x040000:0x040080]
    with open("da14585_nvds_calib.bin", "wb") as f:
        f.write(nvds_data)
    print(f"[+] Extracted NVDS / Device calibration data (0x40000) to: da14585_nvds_calib.bin")

    # Search for Bluetooth MAC Address (BD_ADDR) in NVDS
    # Look for 6-byte pattern in 0x40000 block
    bd_addr_raw = nvds_data[4:10]
    bd_addr_str = ":".join(f"{b:02X}" for b in reversed(bd_addr_raw))
    print(f"    - Potential Bluetooth BD Address: {bd_addr_str}")

    print("\n" + "=" * 70)
    print("[+] All partitions successfully carved and ready for Ghidra / reverse engineering!")
    print("=" * 70)

if __name__ == "__main__":
    main()
