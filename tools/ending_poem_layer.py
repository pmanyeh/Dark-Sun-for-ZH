#!/usr/bin/env python3
"""Chinese text for the two poems of the ending (CINE.GFF BMP 10 and 11).

The ending is cinematic 100 of the player at overlay 0x568F0 (switch table
cs:073C = file 0x56BCC: ids 0, 1, 100, 200, 300), which plays CINE scenes 11,
12 and 13; the poems are laid over those scenes. Unlike the opening scrolls
they are not full frames: each BMP is one frame whose spans cover only the
lettering (rows 10..68), everything else is transparent. The English letters
are outlined in 179 with a 109 body and a 253 (poem 1) or 1 (poem 2) bevel.

The Chinese keeps the same palette indices, so no runtime palette is needed:
Microsoft JhengHei Bold at 14px, thresholded, in 109 with a 179 shadow one
pixel right and down (a full outline fills the gaps between dense Chinese
strokes). The frame is re-encoded with spans only over opaque pixels and zero-padded to
the original chunk length (a single-frame chunk's first u32 is its length).

``preview_ending_on_start`` is for testing only: it points cinematic 1
(START GAME) at the ending's case, so the poems can be checked without
finishing the game. It must never go into a normal build.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from .intro_scroll_layer import _rle_codes
except ImportError:
    from intro_scroll_layer import _rle_codes

FONT_PATH = Path("C:/Windows/Fonts/msjhbd.ttc")  # Microsoft JhengHei Bold
FONT_SIZE = 14
THRESHOLD = 128
LEFT, TOP, PITCH = 24, 7, 17
FILL, SHADOW = 109, 179
MAX_SPAN_PIXELS = 241

# (BMP id, source sha256, lines)
POEMS = (
    (10, "596c0f21ca2253e0972a40ca5221b7c51eeacce446d7770bbf50b985d9c6a26f", ("你高舉屠龍劍，", "立於克拉西斯殘破的屍身之上。", "他的殘軍四散奔逃，", "傳奇，就此展開……")),
    (11, "134ab030cd13dac908bf7e115c331890df1e6244ecac5a854f5b3a1d54e132dd", ("他們將自荒漠而來，", "攜著遠古的器物。", "歲月攔不住他們，", "一切祕密終將吐露。")),
)

# Cinematic switch (overlay segment at file 0x56490): ids at cs:073C
# (file 0x56BCC), target words at file 0x56BD6.
SWITCH_TARGETS = 0x56BD6
START_GAME_CASE = 0x0532  # 0x569C2, scenes 9 and 10
ENDING_CASE = 0x0574      # 0x56A04, scenes 11, 12 and 13


def text_mask(text: str) -> list[list[bool]]:
    font = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)
    width = font.getbbox(text)[2] + 2
    image = Image.new("L", (width, FONT_SIZE + 4), 0)
    ImageDraw.Draw(image).text((0, 0), text, font=font, fill=255)
    return [[image.getpixel((x, y)) >= THRESHOLD for x in range(width)] for y in range(image.height)]


def render_poem(lines) -> list[list[int]]:
    """A 320x200 image, 0 = transparent, the lines in FILL with a SHADOW."""
    canvas = [[0] * 320 for _ in range(200)]
    for index, line in enumerate(lines):
        mask = text_mask(line)
        height, width = len(mask), len(mask[0])
        top = TOP + index * PITCH
        on = lambda x, y: 0 <= y < height and 0 <= x < width and mask[y][x]  # noqa: E731
        for y in range(height + 1):
            for x in range(width + 1):
                cx, cy = LEFT + x, top + y
                if not (0 <= cx < 320 and 0 <= cy < 200):
                    continue
                if on(x, y):
                    canvas[cy][cx] = FILL
                elif on(x - 1, y) or on(x, y - 1) or on(x - 1, y - 1):
                    canvas[cy][cx] = SHADOW
    if any(canvas[y][319] for y in range(200)):
        raise ValueError("an ending poem line runs off the right edge")
    return canvas


def encode_transparent_frame(image: list[list[int]]) -> bytes:
    """Frame body with spans over the opaque pixels only; empty rows are omitted."""
    width = len(image[0])
    body = bytearray(struct.pack("<2H", width, len(image)))
    for number, row in enumerate(image):
        spans = []
        x = 0
        while x < width:
            if row[x] == 0:
                x += 1
                continue
            start = x
            while x < width and row[x] != 0 and x - start < MAX_SPAN_PIXELS:
                x += 1
            end = x
            codes = _rle_codes(row[start:end])
            while len(codes) > 0xFF:
                end -= 8
                codes = _rle_codes(row[start:end])
            x = end
            spans.append((start, end - start, codes))
        if not spans:
            continue
        body.append(number)
        for index, (start, count, codes) in enumerate(spans):
            flags = (0x01 if start >= 256 else 0) | (0x80 if index == len(spans) - 1 else 0)
            body += bytes((start & 0xFF, flags, count, len(codes))) + codes
    body.append(0xFF)
    return bytes(body)


def single_frame_chunk(original: bytes, body: bytes) -> bytes:
    """The original header (u32 length, u16 frame count 1, u32 offset 10) and the new
    frame, zero-padded to the original length so the chunk size never changes."""
    if struct.unpack_from("<IHI", original, 0) != (len(original), 1, 10):
        raise ValueError("not a single-frame BMP chunk")
    if 10 + len(body) > len(original):
        raise ValueError(f"new poem frame is {len(body)} bytes, the original holds {len(original) - 10}")
    return original[:10] + body + bytes(len(original) - 10 - len(body))


def build_ending_poems(extract) -> dict[int, bytes]:
    """extract(bmp_id) -> original BMP chunk; returns the new BMP chunks."""
    if not FONT_PATH.is_file():
        raise ValueError(f"missing font for the ending poems: {FONT_PATH}")
    chunks = {}
    for bmp_id, sha256, lines in POEMS:
        original = extract(bmp_id)
        if sha256 and hashlib.sha256(original).hexdigest() != sha256:
            raise ValueError(f"CINE BMP {bmp_id} fingerprint does not match")
        chunks[bmp_id] = single_frame_chunk(original, encode_transparent_frame(render_poem(lines)))
    return chunks


def preview_ending_on_start(image: bytes) -> bytes:
    """TEST ONLY: START GAME plays the ending cinematic instead of the opening."""
    site = SWITCH_TARGETS + 2  # id 1
    if struct.unpack_from("<H", image, site)[0] != START_GAME_CASE:
        raise ValueError("cinematic switch table does not hold the expected START GAME target")
    return image[:site] + struct.pack("<H", ENDING_CASE) + image[site + 2:]
