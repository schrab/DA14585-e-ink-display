from PIL import Image, ImageDraw, ImageFont

WIDTH = 400
HEIGHT = 300

# Create RGB image with white background
img = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
draw = ImageDraw.Draw(img)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED   = (255, 0, 0)

# 1. Outer borders: Black outer + Red inner
draw.rectangle([4, 4, WIDTH - 5, HEIGHT - 5], outline=BLACK, width=2)
draw.rectangle([7, 7, WIDTH - 8, HEIGHT - 8], outline=RED, width=2)

# 2. Header banner: Solid RED with white text
draw.rectangle([11, 11, WIDTH - 12, 48], fill=RED)
draw.text((25, 18), "DA14585 3-COLOR EPD TEST (BLACK + RED)", fill=WHITE)

# 3. Hardware specifications with color accents
draw.text((20, 58), "Panel: 4.2\" Tri-Color EPD (Solomon SSD1619)", fill=BLACK)
draw.text((20, 75), "Resolution: 400 x 300 pixels | Dialog DA14585", fill=BLACK)

# Red accent line
draw.line([(20, 96), (WIDTH - 20, 96)], fill=RED, width=2)

# 4. Color Swatch demonstration boxes
# Swatch 1: White
draw.rectangle([20, 108, 120, 148], outline=BLACK, width=2, fill=WHITE)
draw.text((38, 120), "WHITE", fill=BLACK)

# Swatch 2: Solid Black
draw.rectangle([140, 108, 240, 148], outline=BLACK, width=2, fill=BLACK)
draw.text((158, 120), "BLACK", fill=WHITE)

# Swatch 3: Solid Red
draw.rectangle([260, 108, 360, 148], outline=BLACK, width=2, fill=RED)
draw.text((282, 120), "RED", fill=WHITE)

# Red accent box around GPIO info
draw.rectangle([16, 160, WIDTH - 17, 215], outline=RED, width=2)
draw.text((24, 165), "TRI-COLOR REVERSE-ENGINEERED GPIO PINOUT:", fill=RED)
draw.text((24, 182), "P2_3: PWR_EN  |  P2_0: BUSY    |  P0_7: RST", fill=BLACK)
draw.text((24, 198), "P2_1: CS      |  P0_5: D/C     |  P0_0: CLK  |  P0_6: MOSI", fill=BLACK)

# 5. Checkerboard: Alternating Black and Red squares!
box_size = 12
y_start = 228
for r in range(4):
    for c in range(25):
        x = 20 + c * box_size
        y = y_start + r * box_size
        if (r + c) % 3 == 0:
            draw.rectangle([x, y, x + box_size - 1, y + box_size - 1], fill=BLACK)
        elif (r + c) % 3 == 1:
            draw.rectangle([x, y, x + box_size - 1, y + box_size - 1], fill=RED)
        else:
            draw.rectangle([x, y, x + box_size - 1, y + box_size - 1], outline=BLACK, fill=WHITE)

# Red status stamp
draw.rectangle([325, 230, 385, 274], outline=RED, width=2)
draw.text((332, 238), "RED", fill=RED)
draw.text((332, 252), "ACTIVE", fill=RED)

# Save preview PNG for inspection
img.save("test_pattern_red_400x300.png")
print("[+] Saved preview to test_pattern_red_400x300.png")

# Generate the two 15,000-byte buffers:
# BW RAM (0x24): 1 = White/Red, 0 = Black
# RED RAM (0x26): 1 = Red, 0 = Non-Red (Black/White)

bw_bytes = bytearray()
red_bytes = bytearray()

for y in range(HEIGHT):
    for x_byte in range(WIDTH // 8):
        bw_val = 0
        red_val = 0
        for b in range(8):
            px = img.getpixel((x_byte * 8 + b, y))
            # Detect color:
            # Red: R > 150 and G < 100 and B < 100
            # Black: R < 100 and G < 100 and B < 100
            # White: R > 200 and G > 200 and B > 200
            is_red = (px[0] > 150 and px[1] < 100 and px[2] < 100)
            is_black = (px[0] < 100 and px[1] < 100 and px[2] < 100)

            bit_pos = 7 - b

            # In BW RAM (0x24): 1 is White, 0 is Black. Red is set to 1 (white plane)
            if not is_black:
                bw_val |= (1 << bit_pos)

            # In RED RAM (0x26): 1 is Red, 0 is Non-Red
            if is_red:
                red_val |= (1 << bit_pos)

        bw_bytes.append(bw_val)
        red_bytes.append(red_val)

with open("test_bw_framebuffer_15k.bin", "wb") as f:
    f.write(bw_bytes)
with open("test_red_framebuffer_15k.bin", "wb") as f:
    f.write(red_bytes)

print(f"[+] Exported BW framebuffer:  {len(bw_bytes)} bytes to test_bw_framebuffer_15k.bin")
print(f"[+] Exported RED framebuffer: {len(red_bytes)} bytes to test_red_framebuffer_15k.bin")
