#!/usr/bin/env python3
"""Inspect, preview, and patch Dark Sun's RESOURCE.GFF FONT-100 chunk.

The DS1 FONT payload is a compact single-byte bitmap font:

    u16 glyph_count
    u16 glyph_height
    u32 reserved
    u8  character_map[glyph_count]
    u16 glyph_offsets[glyph_count]  # absolute offsets in this payload
    glyph records                  # u16 width + width*height palette bytes

This tool intentionally operates on an extracted FONT chunk.  Use gff-cat to
extract or replace the chunk in a copied RESOURCE.GFF.
"""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Font100:
    count: int
    height: int
    reserved: bytes
    character_map: bytes
    glyphs: list[tuple[int, bytes]]

    @classmethod
    def parse(cls, data: bytes) -> "Font100":
        if len(data) < 8:
            raise ValueError("FONT payload is shorter than its header")
        count, height = struct.unpack_from("<HH", data, 0)
        reserved = data[4:8]
        table_end = 8 + count + count * 2
        if not count or not height or table_end > len(data):
            raise ValueError("invalid FONT dimensions or tables")

        character_map = data[8 : 8 + count]
        offsets = list(struct.unpack_from(f"<{count}H", data, 8 + count))
        if offsets != sorted(offsets):
            raise ValueError("glyph offsets are not monotonic")
        if offsets[0] < table_end or offsets[-1] >= len(data):
            raise ValueError("glyph offsets fall outside the payload")

        glyphs: list[tuple[int, bytes]] = []
        ends = offsets[1:] + [len(data)]
        for index, (start, end) in enumerate(zip(offsets, ends)):
            if end - start < 2:
                raise ValueError(f"glyph {index} is shorter than its width field")
            width = struct.unpack_from("<H", data, start)[0]
            pixels = data[start + 2 : end]
            expected = width * height
            if len(pixels) != expected:
                raise ValueError(
                    f"glyph {index} has {len(pixels)} pixels; expected {expected}"
                )
            glyphs.append((width, pixels))

        return cls(count, height, reserved, character_map, glyphs)

    def build(self) -> bytes:
        table_end = 8 + self.count + self.count * 2
        records: list[bytes] = []
        offsets: list[int] = []
        cursor = table_end
        for width, pixels in self.glyphs:
            if len(pixels) != width * self.height:
                raise ValueError("glyph dimensions do not match pixel data")
            record = struct.pack("<H", width) + pixels
            if cursor > 0xFFFF:
                raise ValueError("FONT offset exceeds the 16-bit table")
            offsets.append(cursor)
            records.append(record)
            cursor += len(record)
        return b"".join(
            (
                struct.pack("<HH", self.count, self.height),
                self.reserved,
                self.character_map,
                struct.pack(f"<{self.count}H", *offsets),
                *records,
            )
        )


ZHONG_8X9 = (
    "........",
    "...#....",
    ".#####..",
    ".#.#.#..",
    ".#.#.#..",
    ".#####..",
    "...#....",
    "...#....",
    "........",
)


def bitmap_with_shadow(rows: tuple[str, ...], height: int) -> tuple[int, bytes]:
    if len(rows) != height or not rows:
        raise ValueError(f"bitmap must contain exactly {height} rows")
    width = len(rows[0])
    if not width or any(len(row) != width for row in rows):
        raise ValueError("bitmap rows must have one non-zero width")

    pixels = bytearray(width * height)
    foreground: set[tuple[int, int]] = set()
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            if value == "#":
                foreground.add((x, y))
                pixels[y * width + x] = 0xFE
            elif value != ".":
                raise ValueError(f"unsupported bitmap character: {value!r}")

    # Match the original font's foreground (FE) and brown shadow (14) style.
    for x, y in foreground:
        shadow = (x + 1, y + 1)
        if shadow not in foreground and shadow[0] < width and shadow[1] < height:
            pixels[shadow[1] * width + shadow[0]] = 0x14
    return width, bytes(pixels)


def rasterize_character(
    character: str,
    font_path: Path,
    font_size: int,
    pixel_width: int,
    glyph_height: int,
    advance: int,
    threshold: int,
) -> tuple[int, bytes]:
    """Rasterize one Unicode character into a FONT-100 palette record."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("replace-text requires Pillow (`python -m pip install Pillow`)") from exc

    if len(character) != 1:
        raise ValueError("each mapping entry must contain exactly one Unicode character")
    if advance < pixel_width:
        raise ValueError("advance must be at least pixel-width")
    font = ImageFont.truetype(str(font_path), font_size)
    left, top, right, bottom = font.getbbox(character)
    source_width = max(1, right - left)
    source_height = max(1, bottom - top)
    source = Image.new("L", (source_width, source_height), 0)
    ImageDraw.Draw(source).text((-left, -top), character, font=font, fill=255)
    content_box = source.getbbox()
    if content_box is None:
        raise ValueError(f"font produced an empty glyph for U+{ord(character):04X}")
    source = source.crop(content_box)
    resized = source.resize((pixel_width, glyph_height), Image.Resampling.LANCZOS)
    pixels = bytearray(advance * glyph_height)
    for y in range(glyph_height):
        for x in range(pixel_width):
            if resized.getpixel((x, y)) >= threshold:
                pixels[y * advance + x] = 0xFE
    return advance, bytes(pixels)


def convert_font_height(font: Font100, target_height: int, align: str) -> None:
    """Pad every existing glyph to a new global height without resampling it."""
    if target_height < font.height:
        raise ValueError(
            f"target height {target_height} is smaller than source height {font.height}; "
            "height conversion only pads existing glyphs"
        )
    if target_height == font.height:
        return
    gap = target_height - font.height
    if align == "top":
        y_offset = 0
    elif align == "center":
        y_offset = gap // 2
    elif align == "bottom":
        y_offset = gap
    else:
        raise ValueError(f"unsupported vertical alignment: {align}")

    converted: list[tuple[int, bytes]] = []
    for width, pixels in font.glyphs:
        padded = bytearray(width * target_height)
        for y in range(font.height):
            source = y * width
            destination = (y + y_offset) * width
            padded[destination : destination + width] = pixels[source : source + width]
        converted.append((width, bytes(padded)))
    font.height = target_height
    font.glyphs = converted


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def write_rgb_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    if len(rgb) != width * height * 3:
        raise ValueError("RGB buffer size does not match PNG dimensions")
    scanlines = b"".join(
        b"\x00" + rgb[y * width * 3 : (y + 1) * width * 3]
        for y in range(height)
    )
    png = b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            png_chunk(b"IDAT", zlib.compress(scanlines, 9)),
            png_chunk(b"IEND", b""),
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def render_atlas(font: Font100, output: Path, scale: int) -> None:
    columns = 16
    rows = (font.count + columns - 1) // columns
    cell_width = max(width for width, _ in font.glyphs) + 2
    cell_height = font.height + 2
    width = columns * cell_width
    height = rows * cell_height
    background = (24, 24, 30)
    foreground = (246, 244, 224)
    shadow = (124, 70, 48)
    grid = (55, 55, 65)
    rgb = bytearray(background * (width * height))

    def set_pixel(x: int, y: int, colour: tuple[int, int, int]) -> None:
        offset = (y * width + x) * 3
        rgb[offset : offset + 3] = bytes(colour)

    for index, (glyph_width, pixels) in enumerate(font.glyphs):
        cell_x = (index % columns) * cell_width
        cell_y = (index // columns) * cell_height
        for x in range(cell_width):
            set_pixel(cell_x + x, cell_y, grid)
        for y in range(cell_height):
            set_pixel(cell_x, cell_y + y, grid)
        for y in range(font.height):
            for x in range(glyph_width):
                value = pixels[y * glyph_width + x]
                if value == 0:
                    continue
                colour = foreground if value == 0xFE else shadow if value == 0x14 else (220, 80, 220)
                set_pixel(cell_x + 1 + x, cell_y + 1 + y, colour)

    if scale > 1:
        scaled_width = width * scale
        scaled_height = height * scale
        scaled = bytearray(scaled_width * scaled_height * 3)
        for y in range(height):
            row = rgb[y * width * 3 : (y + 1) * width * 3]
            expanded = b"".join(row[x : x + 3] * scale for x in range(0, len(row), 3))
            for dy in range(scale):
                start = ((y * scale + dy) * scaled_width) * 3
                scaled[start : start + len(expanded)] = expanded
        width, height, rgb = scaled_width, scaled_height, scaled

    write_rgb_png(output, width, height, bytes(rgb))


def load_font(path: Path) -> Font100:
    return Font100.parse(path.read_bytes())


def command_info(args: argparse.Namespace) -> None:
    font = load_font(args.input)
    widths = [width for width, _ in font.glyphs]
    values = sorted({value for _, pixels in font.glyphs for value in pixels})
    print(f"glyphs={font.count}")
    print(f"height={font.height}")
    print(f"width_min={min(widths)}")
    print(f"width_max={max(widths)}")
    print(f"palette_values={','.join(f'0x{x:02X}' for x in values)}")
    print(f"identity_character_map={font.character_map == bytes(range(font.count))}")


def command_render(args: argparse.Namespace) -> None:
    font = load_font(args.input)
    render_atlas(font, args.output, args.scale)
    print(args.output)


def command_replace(args: argparse.Namespace) -> None:
    font = load_font(args.input)
    if font.height != len(ZHONG_8X9):
        raise ValueError(f"zhong preset requires height {len(ZHONG_8X9)}, got {font.height}")
    code = int(args.code, 0)
    if not 0 <= code < font.count:
        raise ValueError(f"glyph code must be between 0 and {font.count - 1}")
    font.glyphs[code] = bitmap_with_shadow(ZHONG_8X9, font.height)
    payload = font.build()
    # A mandatory parse-after-build check catches offset or size mistakes.
    reparsed = Font100.parse(payload)
    if reparsed.glyphs[code] != font.glyphs[code]:
        raise ValueError("rebuilt glyph did not survive round-trip validation")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(args.output)


def command_replace_text(args: argparse.Namespace) -> None:
    font = load_font(args.input)
    if args.height is not None:
        convert_font_height(font, args.height, args.vertical_align)
    codes = [ord(value) for value in args.codes]
    characters = list(args.text)
    if len(codes) != len(characters):
        raise ValueError(
            f"--codes has {len(codes)} entries but --text has {len(characters)} characters"
        )
    if len(set(codes)) != len(codes):
        raise ValueError("--codes must not contain duplicates")
    if any(code >= font.count for code in codes):
        raise ValueError(f"all mapping codes must be below {font.count}")

    mapping: list[dict[str, object]] = []
    for code, character in zip(codes, characters):
        font.glyphs[code] = rasterize_character(
            character,
            args.font,
            args.font_size,
            args.pixel_width,
            font.height,
            args.advance,
            args.threshold,
        )
        mapping.append(
            {
                "byte": code,
                "byte_hex": f"0x{code:02X}",
                "placeholder": chr(code),
                "character": character,
                "unicode": f"U+{ord(character):04X}",
            }
        )

    payload = font.build()
    reparsed = Font100.parse(payload)
    for code in codes:
        if reparsed.glyphs[code] != font.glyphs[code]:
            raise ValueError(f"rebuilt glyph 0x{code:02X} failed round-trip validation")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    if args.mapping_output:
        args.mapping_output.parent.mkdir(parents=True, exist_ok=True)
        args.mapping_output.write_text(
            json.dumps({"text": args.text, "codes": args.codes, "mapping": mapping}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
    for item in mapping:
        print(f"{item['byte_hex']} {item['placeholder']} -> {item['character']} {item['unicode']}")
    print(args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="validate and describe a FONT-100 payload")
    info.add_argument("input", type=Path)
    info.set_defaults(func=command_info)

    render = subparsers.add_parser("render", help="render all glyphs as a PNG atlas")
    render.add_argument("input", type=Path)
    render.add_argument("output", type=Path)
    render.add_argument("--scale", type=int, default=4)
    render.set_defaults(func=command_render)

    replace = subparsers.add_parser("replace-zhong", help="replace one glyph with an 8x9 中 test bitmap")
    replace.add_argument("input", type=Path)
    replace.add_argument("output", type=Path)
    replace.add_argument("--code", default="0x40", help="glyph code to replace (default: 0x40 / @)")
    replace.set_defaults(func=command_replace)

    replace_text = subparsers.add_parser(
        "replace-text", help="rasterize Unicode characters into temporary single-byte glyph slots"
    )
    replace_text.add_argument("input", type=Path)
    replace_text.add_argument("output", type=Path)
    replace_text.add_argument("--text", required=True, help="Unicode characters to rasterize")
    replace_text.add_argument("--codes", required=True, help="one placeholder byte character per Unicode character")
    replace_text.add_argument("--font", required=True, type=Path, help="TrueType/OpenType font used as the test source")
    replace_text.add_argument("--font-size", type=int, default=16)
    replace_text.add_argument(
        "--height", type=int, help="pad the entire font to this global height before replacing glyphs"
    )
    replace_text.add_argument(
        "--vertical-align",
        choices=("top", "center", "bottom"),
        default="center",
        help="alignment of original glyph rows when --height adds padding",
    )
    replace_text.add_argument("--pixel-width", type=int, default=8)
    replace_text.add_argument("--advance", type=int, default=9)
    replace_text.add_argument("--threshold", type=int, default=100)
    replace_text.add_argument("--mapping-output", type=Path)
    replace_text.set_defaults(func=command_replace_text)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "scale", 1) < 1:
        parser.error("--scale must be at least 1")
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
