#!/usr/bin/env python3
"""
Dithering / halftone converter for the SSD1619 tri-colour panel.

Why this exists
---------------
The panel has exactly three states per pixel, from the two RAM planes:

    BW (0x24)  RED (0x26)   colour
    ---------------------------------
       0          0         black
       1          0         white
       1          1         red
      (0,1) is never emitted

A hard-threshold converter cannot represent anything in between, so a washed-out pink
like the (240,80,80) in gfx/pogromirovay-2.png has only two choices: call it red (too
saturated) or white (loses the image). The first poster's solid (185,0,3) thresholded
fine; half of the second poster's red-hue pixels fail the `g < 110 and b < 110` test and
silently become white.

But the panel is 400x300 and the eye averages over distance, so intermediate tones can be
*faked spatially* by mixing two palette colours as a halftone. Red-on-white reads as pink;
red-on-black reads as maroon. That is what this module does.

Two methods
-----------
  bayer  Ordered 8x8 Bayer threshold. Regular, reproducible, reads as a classic halftone.
         Preferred default: deterministic, so uploads stay byte-exact and verifiable.
  fs     Floyd-Steinberg error diffusion. Organic, better for photographic content, but
         noise-dependent.

Both do palette matching in linear light with a luminance-weighted metric, so dark regions
(laptops, outlines) keep their detail instead of over-dithering.

Usage
-----
  ./venv/bin/python dither_convert.py -i gfx/pogromirovay-2.png -o out.bin --preview
  ./venv/bin/python dither_convert.py -i in.png --method fs --red 200 20 20
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

WIDTH = 400
HEIGHT = 300
PLANE_SIZE = WIDTH * HEIGHT // 8  # 15000
TOTAL = PLANE_SIZE * 2  # 30000

# Palette in sRGB 0-255. RED is the on-panel chroma, not the source's red; override
# with --red if you have a better reference sample from the physical display.
DEFAULT_RED = (196, 32, 24)

# Rec.709 luma weights, used so the distance metric matches perceived brightness.
LW = np.array([0.2126, 0.7152, 0.0722], dtype=np.float64)

BAYER8 = np.array(
    [
        [0, 32, 8, 40, 2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44, 4, 36, 14, 46, 6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [3, 35, 11, 43, 1, 33, 9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47, 7, 39, 13, 45, 5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21],
    ],
    dtype=np.float64,
)


def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * (c ** (1 / 2.4)) - 0.055)
    return np.clip(s * 255.0, 0, 255)


def load_and_fit(path: str, crop: bool = True) -> np.ndarray:
    """Load, centre-crop to the panel's 4:3, and LANCZOS-downscale to 400x300.

    The crop matters: progromirovay-2.png is 2400x1728 (1.3889) against the panel's
    1.3333, so a bare resize squashes the horizontal by 4%. Downscaling happens *before*
    dithering so LANCZOS does the anti-aliasing and the dither only handles what is left.
    """
    img = Image.open(path).convert("RGB")
    if crop:
        w, h = img.size
        target = WIDTH / HEIGHT
        if w / h > target:  # too wide -> trim sides
            nw = int(round(h * target))
            img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:  # too tall -> trim top/bottom
            nh = int(round(w / target))
            img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float64)


def _palette_linear(red) -> np.ndarray:
    # NOTE: build in 0-255 and let _srgb_to_linear do the single /255. Pre-dividing
    # here would normalise twice and linearise red down to ~0, making it identical to
    # black in the metric.
    pal = np.array([[0.0, 0.0, 0.0], [255.0, 255.0, 255.0], list(red)], dtype=np.float64)
    return _srgb_to_linear(pal)


def _dist_field(img_lin: np.ndarray, pal_lin: np.ndarray) -> np.ndarray:
    """(H,W,3) weighted distance from every pixel to every palette entry."""
    d = img_lin[:, :, None, :] - pal_lin[None, None, :, :]
    return np.sqrt((d * d * LW).sum(axis=-1))  # (H,W,3)


def dither_bayer(img_lin: np.ndarray, pal_lin: np.ndarray) -> np.ndarray:
    """Ordered dithering: pick between the two nearest palette colours per pixel.

    For each pixel, t is the projection of the target onto the segment joining the two
    nearest colours, so t~0 means "essentially colour A" and t~1 means "essentially B".
    The Bayer threshold decides which side of t the pixel lands on, which is what turns
    a mid-tone region into a regular halftone.
    """
    h, w, _ = img_lin.shape
    dist = _dist_field(img_lin, pal_lin)
    order = np.argsort(dist, axis=-1)
    n1 = order[:, :, 0]
    n2 = order[:, :, 1]
    d1 = np.take_along_axis(dist, n1[:, :, None], axis=-1)[:, :, 0]
    d2 = np.take_along_axis(dist, n2[:, :, None], axis=-1)[:, :, 0]

    c1 = pal_lin[n1]
    c2 = pal_lin[n2]
    seg = c1 - c2
    seg_len2 = (seg * seg).sum(axis=-1)
    seg_len2[seg_len2 == 0] = 1e-9
    # Projection along the segment running from c2 (=n2) to c1 (=n1):
    #   t = 0  -> target sits on c2  -> want n2
    #   t = 1  -> target sits on c1  -> want n1
    t = ((img_lin - c2) * seg).sum(axis=-1) / seg_len2
    t = np.clip(t, 0.0, 1.0)

    thr = ((BAYER8[np.arange(h)[:, None] % 8, np.arange(w)[None, :] % 8]) + 0.5) / 64.0
    return np.where(t < thr, n2, n1).astype(np.uint8)


def dither_fs(img_lin: np.ndarray, pal_lin: np.ndarray) -> np.ndarray:
    """Floyd-Steinberg error diffusion, 4-tap kernel."""
    h, w, _ = img_lin.shape
    out = np.zeros((h, w), dtype=np.uint8)
    work = img_lin.copy()
    for y in range(h):
        for x in range(w):
            px = work[y, x]
            dist = np.sqrt((((px - pal_lin) ** 2) * LW).sum(axis=-1))
            k = int(np.argmin(dist))
            out[y, x] = k
            err = px - pal_lin[k]
            if x + 1 < w:
                work[y, x + 1] += err * (7 / 16)
            if y + 1 < h:
                if x > 0:
                    work[y + 1, x - 1] += err * (3 / 16)
                work[y + 1, x] += err * (5 / 16)
                if x + 1 < w:
                    work[y + 1, x + 1] += err * (1 / 16)
    return out


def pack(idx: np.ndarray) -> bytes:
    """Pack a (H,W) palette-index map into the two RAM planes, MSB-first per byte.

    Matches the existing convention: bit_pos = 7 - b within each byte, bytes in
    left-to-right scanline order.
    """
    h, w = idx.shape
    if (h, w) != (HEIGHT, WIDTH):
        raise ValueError(f"expected {(HEIGHT, WIDTH)}, got {(h, w)}")
    bw = np.where(idx == 0, 0, 1).astype(np.uint8)      # 0 = black
    red = np.where(idx == 2, 1, 0).astype(np.uint8)     # 1 = red
    bits_bw = np.packbits(bw.reshape(-1), bitorder="big")
    bits_red = np.packbits(red.reshape(-1), bitorder="big")
    out = bits_bw.tobytes() + bits_red.tobytes()
    if len(out) != TOTAL:
        raise ValueError(f"packed {len(out)} B, expected {TOTAL}")
    return out


def convert(path: str, method: str = "bayer", red=DEFAULT_RED, crop: bool = True) -> bytes:
    img = load_and_fit(path, crop=crop)
    img_lin = _srgb_to_linear(img)
    pal = _palette_linear(red)
    if method == "bayer":
        idx = dither_bayer(img_lin, pal)
    elif method == "fs":
        idx = dither_fs(img_lin, pal)
    elif method == "none":
        idx = np.argmin(_dist_field(img_lin, pal), axis=-1).astype(np.uint8)
    else:
        raise ValueError(f"unknown method {method!r}")
    return pack(idx), idx


def to_preview(idx: np.ndarray) -> Image.Image:
    out = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    out[idx == 0] = (0, 0, 0)
    out[idx == 1] = (255, 255, 255)
    out[idx == 2] = DEFAULT_RED
    return Image.fromarray(out, "RGB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--image", required=True)
    ap.add_argument("-o", "--out", default=None, help="write the 30,000-byte buffer here")
    ap.add_argument("--method", default="bayer", choices=["bayer", "fs", "none"])
    ap.add_argument("--red", nargs=3, type=int, default=list(DEFAULT_RED), metavar=("R", "G", "B"))
    ap.add_argument("--preview", default=None, help="write a 400x300 preview PNG here")
    ap.add_argument("--no-crop", action="store_true", help="skip the 4:3 centre crop")
    a = ap.parse_args()

    if not os.path.exists(a.image):
        print(f"ERROR: no such file: {a.image}", file=sys.stderr)
        return 1

    buf, idx = convert(a.image, a.method, tuple(a.red), crop=not a.no_crop)

    total = WIDTH * HEIGHT
    n_black = int((idx == 0).sum())
    n_white = int((idx == 1).sum())
    n_red = int((idx == 2).sum())
    assert n_black + n_white + n_red == total

    print(f"[+] {a.image}  method={a.method}  crop={'on' if not a.no_crop else 'off'}")
    print(f"[+] buffer {len(buf)} B (BW {PLANE_SIZE} + Red {PLANE_SIZE})")
    print(f"[+] black {n_black:6d} ({n_black/total*100:5.1f}%)")
    print(f"[+] white {n_white:6d} ({n_white/total*100:5.1f}%)")
    print(f"[+] red   {n_red:6d} ({n_red/total*100:5.1f}%)")

    if a.out:
        open(a.out, "wb").write(buf)
        print(f"[+] wrote {a.out}")
    if a.preview:
        to_preview(idx).save(a.preview)
        print(f"[+] wrote {a.preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
