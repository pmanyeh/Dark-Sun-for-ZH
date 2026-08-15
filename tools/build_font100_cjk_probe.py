"""Append a two-bank CJK2 probe to FONT-100.

This does not change the legacy 256-glyph FONT data.  It appends a small,
self-describing CJK2 extension containing the six glyphs used by the
``中文顯示成功`` experiment at ids 0, 1, 2, 256, 257, and 258.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "scratch_test/font_16x15_experiment/FONT-100.zh-16x15.bin"
DEFAULT_OUTPUT = ROOT / "scratch_test/font_16x15_experiment/FONT-100.cjk-probe.bin"
MAGIC = b"CJK2"
HEADER = struct.Struct("<4sHHHHI")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_glyph(payload: bytes, code: int) -> tuple[int, int, bytes]:
    count, height = struct.unpack_from("<HH", payload, 0)
    if not 0 <= code < count:
        raise ValueError(f"glyph code 0x{code:02X} is outside count {count}")
    table = 8 + count
    offset = struct.unpack_from("<H", payload, table + code * 2)[0]
    width = struct.unpack_from("<H", payload, offset)[0]
    pixels = payload[offset + 2 : offset + 2 + width * height]
    if len(pixels) != width * height:
        raise ValueError("source glyph record is truncated")
    return width, height, pixels


def build(payload: bytes) -> tuple[bytes, bytes]:
    if MAGIC in payload:
        raise ValueError("input already contains a CJK2 extension")
    codes = (0x40, 0x23, 0x24, 0x5B, 0x5D, 0x2A)
    glyphs = [extract_glyph(payload, code) for code in codes]
    heights = {height for _, height, _ in glyphs}
    if len(heights) != 1:
        raise ValueError("source glyphs do not share one global height")
    height = heights.pop()

    def make_bank(bank_glyphs: list[tuple[int, int, bytes]]) -> bytes:
        table_offset = 4
        cursor = table_offset + len(bank_glyphs) * 2
        offsets: list[int] = []
        records = bytearray()
        for width, _, pixels in bank_glyphs:
            offsets.append(cursor)
            record = struct.pack("<H", width) + pixels
            records += record
            cursor += len(record)
        if cursor > 0xFFFF:
            raise ValueError("one CJK2 bank exceeds its 16-bit relative-offset range")
        return struct.pack("<HH", len(bank_glyphs), table_offset) + struct.pack(
            f"<{len(offsets)}H", *offsets
        ) + records

    banks = (make_bank(glyphs[:3]), make_bank(glyphs[3:]))
    directory_offset = HEADER.size
    cursor = directory_offset + len(banks) * 2
    bank_offsets: list[int] = []
    body = bytearray()
    for bank in banks:
        bank_offsets.append(cursor)
        body += bank
        cursor += len(bank)
    extension = bytearray(HEADER.pack(MAGIC, 2, len(banks), height, 256, directory_offset))
    extension += struct.pack(f"<{len(bank_offsets)}H", *bank_offsets)
    extension += body
    return payload + bytes(extension), bytes(extension)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.input.resolve().read_bytes()
    result, extension = build(source)
    args.output.resolve().write_bytes(result)

    print(f"source_length={len(source)}")
    print(f"extension_offset=0x{len(source):04X}")
    print(f"extension_length={len(extension)}")
    print(f"result_length={len(result)}")
    print("cjk_ids=0,1,2,256,257,258")
    print("legacy_offset_table_unchanged=true")
    print(f"extension_sha256={sha256(extension)}")
    print(f"result_sha256={sha256(result)}")


if __name__ == "__main__":
    main()
