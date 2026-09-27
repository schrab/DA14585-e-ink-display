"""
DA14585 E-Ink Display Image Loader & Converter
==============================================
Loads any image (PNG, BMP, JPG) exported from Photoshop,
quantizes to the 3 panel colors (White, Black, Red),
generates the dual 15KB framebuffers, and flashes to the 4.2" screen.
"""

import sys
import os
import argparse
from PIL import Image

def convert_photoshop_image(image_path, dither=False, rotate=0):
    if not os.path.exists(image_path):
        print(f"[-] Error: File not found: {image_path}")
        sys.exit(1)

    print(f"[*] Opening image: {image_path}")
    raw_img = Image.open(image_path)
    if raw_img.mode in ("RGBA", "LA") or (raw_img.mode == "P" and "transparency" in raw_img.info):
        raw_rgba = raw_img.convert("RGBA")
        img = Image.new("RGB", raw_rgba.size, (255, 255, 255))
        img.paste(raw_rgba, mask=raw_rgba.split()[3])
    else:
        img = raw_img.convert("RGB")

    # Optional rotation
    if rotate in (90, 180, 270):
        print(f"[*] Rotating image by {rotate} degrees...")
        img = img.rotate(rotate, expand=True)

    # Check dimensions
    WIDTH = 400
    HEIGHT = 300
    if img.size != (WIDTH, HEIGHT):
        print(f"[!] Warning: Image size is {img.size[0]}x{img.size[1]}, resizing to 400x300...")
        img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    else:
        print("[+] Image dimensions match panel resolution: 400 x 300 pixels.")

    bw_bytes = bytearray()
    red_bytes = bytearray()

    # Pre-quantize image
    for y in range(HEIGHT):
        for x_byte in range(WIDTH // 8):
            bw_val = 0
            red_val = 0
            for b in range(8):
                r, g, b_col = img.getpixel((x_byte * 8 + b, y))
                bit_pos = 7 - b

                # Red detection: high red, lower green & blue
                # Handles #FF0000 and dark/light shades of red
                is_red = (r > 130) and (r > g * 1.4) and (r > b_col * 1.4)

                # Black detection: low luminance
                luminance = int(0.299 * r + 0.587 * g + 0.114 * b_col)
                is_black = (luminance < 110) and not is_red

                # In BW RAM (0x24): 1 = White/Red, 0 = Black
                if not is_black:
                    bw_val |= (1 << bit_pos)

                # In RED RAM (0x26): 1 = Red, 0 = Non-Red
                if is_red:
                    red_val |= (1 << bit_pos)

            bw_bytes.append(bw_val)
            red_bytes.append(red_val)

    # Export buffers
    bw_file = "custom_bw_framebuffer.bin"
    red_file = "custom_red_framebuffer.bin"
    with open(bw_file, "wb") as f:
        f.write(bw_bytes)
    with open(red_file, "wb") as f:
        f.write(red_bytes)

    # Save a preview of how the screen will look
    preview = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    for y in range(HEIGHT):
        for x in range(WIDTH):
            byte_idx = (y * 50) + (x // 8)
            bit_mask = 1 << (7 - (x % 8))
            is_bw_white = bool(bw_bytes[byte_idx] & bit_mask)
            is_red_on   = bool(red_bytes[byte_idx] & bit_mask)

            if is_red_on:
                preview.putpixel((x, y), (255, 0, 0))
            elif not is_bw_white:
                preview.putpixel((x, y), (0, 0, 0))
            else:
                preview.putpixel((x, y), (255, 255, 255))

    preview_file = "preview_on_display.png"
    preview.save(preview_file)
    print(f"[+] Exported BW buffer:  {len(bw_bytes)} bytes -> {bw_file}")
    print(f"[+] Exported RED buffer: {len(red_bytes)} bytes -> {red_file}")
    print(f"[+] Saved exact display preview -> {preview_file}")

    return bw_file, red_file

def flash_to_screen(bw_file, red_file):
    print("\n[*] Flashing custom image to physical 4.2\" E-Ink display via SWD...")
    import subprocess
    # Run test_eink_red.py with custom buffers if specified or rewrite buffers
    with open(bw_file, "rb") as f:
        bw_data = f.read()
    with open(red_file, "rb") as f:
        red_data = f.read()

    with open("test_bw_framebuffer_15k.bin", "wb") as f:
        f.write(bw_data)
    with open("test_red_framebuffer_15k.bin", "wb") as f:
        f.write(red_data)

    ret = subprocess.run([sys.executable, "test_eink_red.py"])
    if ret.returncode == 0:
        print("\n[SUCCESS] Image is now displayed permanently on the screen!")
    else:
        print("\n[-] Flashing failed. Check ST-Link connection.")

def main():
    parser = argparse.ArgumentParser(description="Convert and display Photoshop images on DA14585 4.2\" E-Ink")
    parser.add_argument("image", help="Path to Photoshop image file (.png, .bmp, .jpg, etc.)")
    parser.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0, help="Rotate image (0, 90, 180, 270)")
    parser.add_argument("--no-flash", action="store_true", help="Only convert and generate preview without flashing to screen")
    args = parser.parse_args()

    bw_f, red_f = convert_photoshop_image(args.image, rotate=args.rotate)

    if not args.no_flash:
        flash_to_screen(bw_f, red_f)

if __name__ == "__main__":
    main()
