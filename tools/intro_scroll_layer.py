#!/usr/bin/env python3
"""Chinese text on the two parchment scrolls of the opening (CINE.GFF).

Scroll 1 ("The once lush and beautiful world...") is frame 0 of BMA 8 and
plays in the attract intro after the title screen; scroll 2 ("By order of
the Mighty and Omnipotent King Tectuktitlay...") is frame 0 of BMA 9 and
plays after START GAME. Both are full 320x200 frames whose English text is
a single palette index. The text pixels are refilled from the surrounding
parchment and the Chinese is drawn anti-aliased: each edge pixel takes the
colour between ink and parchment from the ramp both palettes already carry
for the parchment's shading.

The palettes are the runtime ones, read from the game's palette buffer
(490F:0000 in DOSBox) while each scroll was on screen; the CINE PAL chunks
hold only fragments of them.
"""

from __future__ import annotations

import hashlib
import random
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from .creation_icon_layer import decode_icon
except ImportError:
    from creation_icon_layer import decode_icon


FONT_PATH = Path("C:/Windows/Fonts/msjhbd.ttc")  # Microsoft JhengHei Bold
FONT_SIZE = 20
SUPERSAMPLE = 4
LEFT, TOP, PITCH = 40, 22, 21
MIN_COVERAGE = 0.1
# The original full-screen frames split each 320-pixel row into spans of
# at most 241 pixels.
MAX_SPAN_PIXELS = 241


def _palette(first: int, values: str) -> dict[int, tuple[int, int, int]]:
    return {first + index: tuple(int(item[j:j + 2], 16) for j in (0, 2, 4)) for index, item in enumerate(values.split())}


# 6-bit DAC values. Scroll 1: torn-edge shading 200..204, ink 205, parchment 206..231.
SCROLL1_PALETTE = _palette(200, (
    "2C0C05 2B0D06 290F07 281008 271109 "
    "28120A 2A140B 2B150D 2C170E 2D180F 2F1A11 301B12 311D14 321F16 332117 352219 36241B 37261C "
    "38281E 3A2A20 3B2C22 3C2E24 3D3027 3F3229 3F322A 3F3329 3F3429 3F3529 3F3528 3F3628 3F3828 3F3B28"
))
# Scroll 2: parchment 105..135, shading ramp 172..185, ink 186.
SCROLL2_PALETTE = {
    **_palette(105, (
        "2B0D06 290F07 281008 271109 28120A 2A140B 2B150D 2C170E 2D180F 2F1A11 301B12 311D14 321F16 "
        "332117 352219 36241B 37261C 38281E 3A2A20 3B2C22 3C2E24 3D3027 3F3229 3F322A 3F3329 3F3429 "
        "3F3529 3F3528 3F3628 3F3828 3F3B28"
    )),
    **_palette(172, (
        "38281E 36241B 352219 332117 321F16 311D14 301B12 2F1A11 2D180F 2C170E 2B150D 2A140B 28120A "
        "281008 290F07"
    )),
}

# (BMA id, source sha256, ink index, parchment refill range, text box, palette, lines)
SCROLLS = (
    (8, "a82486bed1f538835b4eb37cc720314a11383f1fadb90fa93a5989e0f03b0b97", 205, (214, 231),
     (30, 20, 300, 180), SCROLL1_PALETTE,
     ("曾經青翠的亞薩斯，", "如今荒涼而致命。", "巫王統治各城邦，", "為追逐權力，碾碎一切",
      "生命與自由。", "在德拉吉，奴隸以無盡的", "死亡之舞，餵養巫王之力。")),
    (9, "0158609ef2b8ed5bf07bbca100228daf8f2c578ecfe7e1c31530a95ca1bc055e", 186, (121, 131),
     (30, 20, 300, 185), SCROLL2_PALETTE,
     ("奉偉大全能的特克圖克特雷", "王之命，凡能持劍的奴隸，", "皆須在角鬥場中作戰。",
      "死亡，便是角鬥士為軟弱", "付出的代價。", "", "競賽開始！")),
)


def erase_text(image: list[list[int]], ink: int, parchment: tuple[int, int], box) -> list[list[int]]:
    """Refill the ink pixels inside box from nearby parchment pixels."""
    x0, y0, x1, y1 = box
    low, high = parchment
    out = [row[:] for row in image]
    rnd = random.Random(1)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if out[y][x] != ink:
                continue
            candidates = []
            for distance in range(1, 8):
                for xx, yy in ((x - distance, y), (x + distance, y), (x, y - distance), (x, y + distance)):
                    if low <= image[yy][xx] <= high:
                        candidates.append(image[yy][xx])
                if len(candidates) >= 3:
                    break
            out[y][x] = rnd.choice(candidates) if candidates else (low + high) // 2
    return out


def draw_text(image: list[list[int]], lines, ink: int, palette: dict[int, tuple[int, int, int]]) -> list[list[int]]:
    font = ImageFont.truetype(str(FONT_PATH), FONT_SIZE * SUPERSAMPLE)
    height, width = len(image), len(image[0])
    mask = Image.new("L", (width * SUPERSAMPLE, height * SUPERSAMPLE), 0)
    pen = ImageDraw.Draw(mask)
    for number, text in enumerate(lines):
        pen.text((LEFT * SUPERSAMPLE, (TOP + number * PITCH) * SUPERSAMPLE), text, font=font, fill=255)
    coverage = mask.resize((width, height), Image.BOX).load()
    colours = sorted(palette)
    ink_rgb = palette[ink]
    out = [row[:] for row in image]
    for y in range(height):
        for x in range(width):
            amount = coverage[x, y] / 255
            if amount < MIN_COVERAGE:
                continue
            under = palette.get(out[y][x])
            if under is None:
                raise ValueError(f"text reaches pixel ({x},{y}) outside the parchment")
            target = tuple(under[i] * (1 - amount) + ink_rgb[i] * amount for i in range(3))
            out[y][x] = min(colours, key=lambda j: sum((palette[j][i] - target[i]) ** 2 for i in range(3)))
    return out


def _rle_codes(pixels: list[int]) -> bytes:
    """Shortest RLE for one span: repeat codes (odd, 2 bytes) and literal codes (even, 1 + n bytes)."""
    count = len(pixels)
    unreached = 1 << 30
    cost = [0] + [unreached] * count
    step: list[tuple[int, bool]] = [(0, False)] * (count + 1)
    for start in range(count):
        end = start
        while end < count and pixels[end] == pixels[start] and end - start < 128:
            end += 1
            if cost[start] + 2 < cost[end]:
                cost[end], step[end] = cost[start] + 2, (start, True)
        for length in range(1, min(128, count - start) + 1):
            if cost[start] + 1 + length < cost[start + length]:
                cost[start + length], step[start + length] = cost[start] + 1 + length, (start, False)
    codes = []
    end = count
    while end:
        start, repeat = step[end]
        run = end - start
        codes.append(bytes(((run - 1) * 2 + 1, pixels[start])) if repeat else bytes(((run - 1) * 2,)) + bytes(pixels[start:end]))
        end = start
    return b"".join(reversed(codes))


def encode_frame(image: list[list[int]]) -> bytes:
    """A fully opaque frame body: w, h, then every row as spans of at most MAX_SPAN_PIXELS."""
    width = len(image[0])
    body = bytearray(struct.pack("<2H", width, len(image)))
    for number, row in enumerate(image):
        if 0 in row:
            raise ValueError("intro scroll frames are fully opaque")
        body.append(number)
        spans = []
        start = 0
        while start < width:
            end = min(width, start + MAX_SPAN_PIXELS)
            codes = _rle_codes(row[start:end])
            while len(codes) > 0xFF:
                end -= 8
                codes = _rle_codes(row[start:end])
            spans.append((start, end - start, codes))
            start = end
        for index, (x, count, codes) in enumerate(spans):
            flags = (0x01 if x >= 256 else 0) | (0x80 if index == len(spans) - 1 else 0)
            body += bytes((x & 0xFF, flags, count, len(codes))) + codes
    body.append(0xFF)
    return bytes(body)


def replace_frame0(chunk: bytes, body: bytes) -> bytes:
    """Swap frame 0's body in place, zero-padded to its original length.

    The header word at 0 is not the chunk length for the animated BMAs and
    its use is unknown; a longer frame 0 (shifting the later frames) crashed
    the intro right after scroll 1. Keeping the length leaves the header,
    the offset table and every later frame byte for byte.
    """
    count = struct.unpack_from("<H", chunk, 4)[0]
    offsets = sorted(struct.unpack_from(f"<{count}I", chunk, 6))
    first, end = offsets[0], (offsets[1] if count > 1 else len(chunk))
    if len(body) > end - first:
        raise ValueError(f"new frame 0 is {len(body)} bytes, the original slot holds {end - first}")
    return chunk[:first] + body + bytes(end - first - len(body)) + chunk[end:]


def chinese_scroll(chunk: bytes, sha256: str, ink: int, parchment, box, palette, lines) -> bytes:
    if hashlib.sha256(chunk).hexdigest() != sha256:
        raise ValueError("CINE scroll source fingerprint does not match the verified frame")
    width, height, image = decode_icon(chunk)[0]
    image = draw_text(erase_text(image, ink, parchment, box), lines, ink, palette)
    return replace_frame0(chunk, encode_frame(image))


def build_intro_scrolls(extract) -> dict[int, bytes]:
    """extract(bma_id) -> original BMA chunk; returns the new BMA chunks."""
    if not FONT_PATH.is_file():
        raise ValueError(f"missing font for the intro scrolls: {FONT_PATH}")
    return {
        bma_id: chinese_scroll(extract(bma_id), sha256, ink, parchment, box, palette, lines)
        for bma_id, sha256, ink, parchment, box, palette, lines in SCROLLS
    }
