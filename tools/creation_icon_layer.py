#!/usr/bin/env python3
"""Chinese class list and PSI/sphere buttons on the character creation screen.

The class list (ICON 2002-2009), the psionic disciplines (2038-2041), the
clerical spheres (2042-2045) and the VIEW SPHERES / VIEW PSIONICS toggles
(2046/2047) are 7px-tall ICON bitmaps, one per button with the same ID
(re_105 §6). Each ICON has three frames that differ only in their single
text colour (hover, unavailable, available). A button's clickable size is
its ICON's size, so the Chinese ICONs are 10px tall and the buttons in
WIND-3011/3012/3013 move onto 10px rows.
"""

from __future__ import annotations

import hashlib
import struct

try:
    from .cjk_localization_pipeline import glyph_record_for_id
except ImportError:
    from cjk_localization_pipeline import glyph_record_for_id


GLYPH_INK = 0xFE
ROW_HEIGHT = 10
DIAMOND_CLEARANCE = 8

# ICON id -> fixed_ui_labels.csv unit.
CREATION_ICON_UNITS = {
    2002: "UI_class_cleric",
    2003: "UI_class_druid",
    2004: "UI_class_fighter",
    2005: "UI_class_gladiator",
    2006: "UI_class_preserver",
    2007: "UI_class_psionicist",
    2008: "UI_class_ranger",
    2009: "UI_class_thief",
    2038: "UI_creation_kinesis",
    2039: "UI_creation_metab",
    2040: "UI_creation_telepathy",
    2041: "UI_creation_portation",
    2042: "UI_creation_air",
    2043: "UI_creation_earth",
    2044: "UI_creation_fire",
    2045: "UI_creation_water",
    2046: "UI_creation_view_spheres",
    2047: "UI_creation_view_psionics",
}

# (WIND id, source sha256, {button id: (original corner, new corner)}).
# WIND-3011's class list sits at x=217 in screen space; WIND-3012/3013 are
# the PSI/sphere window created at (210, 88). Its four entries stay one
# column (the selection diamond is drawn at a fixed x = 218, from the y
# table at CREATION_DIAMOND_ROWS), 10px apart under the title row; the
# toggle moves up beside the title so all five rows fit the box.
CREATION_LIST_WINDS = (
    (3012, "af542dfcff0309efc388275b92f5c481d86b45050e5c3a1fcfe501dab31dbe89", {
        **{0x07F6 + row: ((7, 15 + 8 * row), (7, 15 + ROW_HEIGHT * row)) for row in range(4)},
        0x07FE: ((7, 47), (50, 3)),
    }),
    (3013, "cceb29a4fe978e3fb0f915d0b15a1e056b6e1403e0c66946ccd9281a4c5d84a6", {
        **{0x07FA + row: ((7, 15 + 8 * row), (7, 15 + ROW_HEIGHT * row)) for row in range(4)},
        0x07FF: ((7, 47), (50, 3)),
    }),
)
CLASS_LIST_BUTTONS = {
    0x07D2 + row: ((217, 10 + 8 * row), (217, 4 + ROW_HEIGHT * row)) for row in range(8)
}


def decode_icon(chunk: bytes) -> list[tuple[int, int, list[list[int]]]]:
    """Decode an ICON chunk into (width, height, rows) frames, top row first."""
    count = struct.unpack_from("<H", chunk, 4)[0]
    offsets = struct.unpack_from(f"<{count}I", chunk, 6)
    frames = []
    for offset in offsets:
        width, height = struct.unpack_from("<2H", chunk, offset)
        image = [[0] * width for _ in range(height)]
        cursor = offset + 4
        for _ in range(height):
            row = chunk[cursor]
            cursor += 1
            if row == 0xFF:
                break
            while True:
                x, flags, _, length = chunk[cursor : cursor + 4]
                cursor += 4
                if flags & 1:
                    x += 256
                end = cursor + length
                while cursor < end:
                    code = chunk[cursor]
                    cursor += 1
                    run = code // 2 + 1
                    if code % 2 == 0:
                        for value in chunk[cursor : cursor + run]:
                            if x < width:
                                image[row][x] = value
                            x += 1
                        cursor += run
                    else:
                        for _ in range(run):
                            if x < width:
                                image[row][x] = chunk[cursor]
                            x += 1
                        cursor += 1
                if flags & 0x80:
                    break
        frames.append((width, height, image))
    return frames


def _rle_codes(pixels: list[int]) -> bytes:
    codes = bytearray()
    index = 0
    while index < len(pixels):
        run = 1
        while index + run < len(pixels) and pixels[index + run] == pixels[index] and run < 128:
            run += 1
        if run >= 2:
            codes += bytes(((run - 1) * 2 + 1, pixels[index]))
            index += run
            continue
        direct = 1
        while index + direct < len(pixels) and direct < 128:
            following = index + direct
            if following + 1 < len(pixels) and pixels[following] == pixels[following + 1]:
                break
            direct += 1
        codes += bytes(((direct - 1) * 2,)) + bytes(pixels[index : index + direct])
        index += direct
    return bytes(codes)


def _rle_row(pixels: list[int]) -> bytes:
    """One span per run of opaque pixels, as the game's own ICONs are stored.

    A span is (x, flags, pixel count, code length, codes); flags 0x01 adds
    256 to x and 0x80 marks the row's last span. The game draws with the
    pixel count, so transparent gaps must be skipped, not encoded as 0.
    """
    spans = []
    x = 0
    while x < len(pixels):
        if not pixels[x]:
            x += 1
            continue
        end = x
        while end < len(pixels) and pixels[end]:
            end += 1
        codes = _rle_codes(pixels[x:end])
        if end - x > 0xFF or len(codes) > 0xFF:
            raise ValueError("ICON span is too wide")
        spans.append((x, end - x, codes))
        x = end
    out = bytearray()
    for number, (start, count, codes) in enumerate(spans):
        flags = (0x01 if start >= 256 else 0) | (0x80 if number == len(spans) - 1 else 0)
        out += bytes((start & 0xFF, flags, count, len(codes))) + codes
    return bytes(out)


def encode_icon(frames: list[tuple[int, int, list[list[int]]]]) -> bytes:
    """Encode frames as an ICON chunk (rows stored top row first)."""
    bodies = []
    for width, height, image in frames:
        body = bytearray(struct.pack("<2H", width, height))
        for row, pixels in enumerate(image):
            if any(pixels):
                body.append(row)
                body += _rle_row(pixels)
        body.append(0xFF)
        while len(body) < 9:
            body.append(0)
        bodies.append(bytes(body))
    header = 4 + 2 + 4 * len(frames)
    offsets, position = [], header
    for body in bodies:
        offsets.append(position)
        position += len(body)
    return struct.pack("<IH", position, len(frames)) + struct.pack(f"<{len(frames)}I", *offsets) + b"".join(bodies)


def _text_mask(ids: tuple[int, ...], banks: dict[int, dict[str, object]]) -> list[list[bool]]:
    """Glyph ink only (no shadow) for a row of 10x10 CJK glyphs."""
    rows = [[] for _ in range(ROW_HEIGHT)]
    for value in ids:
        record = glyph_record_for_id(value, banks)
        width = int.from_bytes(record[:2], "little")
        if len(record) != 2 + width * ROW_HEIGHT:
            raise ValueError("CJB1 glyphs must be 10 rows tall for the creation ICONs")
        for y in range(ROW_HEIGHT):
            rows[y] += [pixel == GLYPH_INK for pixel in record[2 + y * width : 2 + (y + 1) * width]]
    return rows


def chinese_icon(original: bytes, ids: tuple[int, ...], banks: dict[int, dict[str, object]]) -> bytes:
    """Redraw an ICON's text in Chinese, keeping each frame's colour and left margin."""
    frames = decode_icon(original)
    ink = [sorted({value for row in image for value in row} - {0}) for _, _, image in frames]
    if any(len(colours) > 1 for colours in ink):
        raise ValueError("creation ICON frames are expected to use one text colour each")
    margins = [
        min((x for row in image for x, value in enumerate(row) if value), default=None)
        for _, _, image in frames
    ]
    margin = min(value for value in margins if value is not None)
    # The game clears a diamond-sized area at the left of every list button
    # (DIAMOND_CLEARANCE); the English toggles start at x=0 and lose only
    # an unnoticed serif there, a Chinese glyph loses a visible corner.
    margin = max(margin, DIAMOND_CLEARANCE)
    mask = _text_mask(ids, banks)
    width = margin + len(mask[0])
    result = []
    for colours in ink:
        colour = colours[0] if colours else 0
        image = [[0] * margin + [colour if on else 0 for on in row] for row in mask]
        result.append((width, ROW_HEIGHT, image))
    return encode_icon(result)


def build_creation_icons(
    extract, ui_ids: dict[str, tuple[int, ...]], banks: dict[int, dict[str, object]]
) -> dict[int, bytes]:
    """extract(kind, id) -> original chunk bytes; returns the new ICON chunks."""
    return {
        icon_id: chinese_icon(extract("ICON", icon_id), ui_ids[unit], banks)
        for icon_id, unit in CREATION_ICON_UNITS.items()
    }


def move_wind_buttons(source: bytes, sha256: str, label: str, buttons) -> bytes:
    if hashlib.sha256(source).hexdigest() != sha256:
        raise ValueError(f"{label} source fingerprint does not match the verified layout")
    patched = bytearray(source)
    for button_id, (old, new) in buttons.items():
        marker = b"BUTN" + button_id.to_bytes(4, "little")
        if source.count(marker) != 1:
            raise ValueError(f"{label} needs exactly one button {button_id:#06x}")
        offset = source.index(marker) + 8
        if struct.unpack_from("<2H", source, offset) != old:
            raise ValueError(f"{label} button {button_id:#06x} is not at its original position")
        struct.pack_into("<2H", patched, offset, *new)
    return bytes(patched)


# Text buttons keep their label in the BUTN chunk itself: byte 109 of the
# 110-byte button record is the label length and the label follows (no NUL).
# BUTN id -> fixed_ui_labels.csv unit.
BUTTON_TEXT_UNITS = {
    13300: "UI_button_drop",
    13302: "UI_button_split",
    13303: "UI_button_more",
    13304: "UI_button_sell",
    15304: "UI_button_info",
    17301: "UI_button_exit",
    17302: "UI_button_exit",
}
BUTTON_RECORD_BYTES = 110


def base94(ids: tuple[int, ...]) -> bytes:
    return b"".join(bytes((0x5E, 0x21 + value // 94, 0x21 + value % 94)) for value in ids)


def button_text_chunk(original: bytes, ids: tuple[int, ...]) -> bytes:
    """Replace a text button's label with Base94 Chinese."""
    label = original[BUTTON_RECORD_BYTES:]
    if not label or not label.isascii() or original[BUTTON_RECORD_BYTES - 1] != len(label):
        raise ValueError("BUTN chunk has no length-prefixed ASCII label after its record")
    text = base94(ids)
    if len(text) > 0xFF:
        raise ValueError("button label is too long")
    return original[:BUTTON_RECORD_BYTES - 1] + bytes((len(text),)) + text


def build_button_texts(extract, ui_ids: dict[str, tuple[int, ...]]) -> dict[int, bytes]:
    return {
        button_id: button_text_chunk(extract("BUTN", button_id), ui_ids[unit])
        for button_id, unit in BUTTON_TEXT_UNITS.items()
    }
