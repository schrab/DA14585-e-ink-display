from PIL import Image, ImageDraw, ImageFont

WIDTH = 400
HEIGHT = 300

# Create 1-bit monochrome image (0 = Black, 1 = White)
img = Image.new("1", (WIDTH, HEIGHT), 1)  # White background
draw = ImageDraw.Draw(img)

# 1. Outer border
draw.rectangle([4, 4, WIDTH - 5, HEIGHT - 5], outline=0, width=3)
draw.rectangle([8, 8, WIDTH - 9, HEIGHT - 9], outline=0, width=1)

# 2. Header banner
draw.rectangle([12, 12, WIDTH - 13, 50], fill=0)
draw.text((25, 20), "DA14585 E-INK REVERSE-ENGINEERED", fill=1)

# 3. Hardware specifications
draw.text((20, 65), "Panel: 4.2\" Electronic Paper Display (EPD)", fill=0)
draw.text((20, 85), "Resolution: 400 x 300 pixels (15,000 bytes)", fill=0)
draw.text((20, 105), "Controller: Solomon Systech SSD1619 / SSD1683", fill=0)
draw.text((20, 125), "SoC: Dialog DA14585 (ARM Cortex-M0 @ 16 MHz)", fill=0)

# 4. GPIO Pinout box
draw.rectangle([16, 150, WIDTH - 17, 215], outline=0, width=2)
draw.text((24, 155), "GPIO HARDWARE PINOUT:", fill=0)
draw.text((24, 175), "P2_3: PWR_EN  |  P2_0: BUSY    |  P0_7: RST", fill=0)
draw.text((24, 195), "P2_1: CS      |  P0_5: D/C     |  P0_0: CLK  |  P0_6: MOSI", fill=0)

# 5. Checkerboard test pattern at bottom
box_size = 12
y_start = 230
for r in range(4):
    for c in range(30):
        if (r + c) % 2 == 0:
            x = 20 + c * box_size
            y = y_start + r * box_size
            draw.rectangle([x, y, x + box_size - 1, y + box_size - 1], fill=0)

draw.text((20 + 31 * box_size, 245), "OK!", fill=0)

# Save preview PNG for inspection
img.save("test_pattern_400x300.png")
print("[+] Created test_pattern_400x300.png successfully!")

# Convert to raw 1-bit scanline buffer (50 bytes per line * 300 lines = 15,000 bytes)
# In standard E-Ink bitmap: 1 bit per pixel.
# In SSD1619: byte format is MSB first (bit 7 = leftmost pixel).
raw_bytes = bytearray()
for y in range(HEIGHT):
    for x_byte in range(WIDTH // 8):
        byte_val = 0
        for b in range(8):
            px = img.getpixel((x_byte * 8 + b, y))
            # 1 for white, 0 for black (or inverted depending on driver mode)
            if px != 0:
                byte_val |= (1 << (7 - b))
        raw_bytes.append(byte_val)

with open("test_framebuffer_15k.bin", "wb") as f:
    f.write(raw_bytes)

print(f"[+] Exported 15,000 bytes framebuffer to test_framebuffer_15k.bin (Size: {len(raw_bytes)} bytes)")
