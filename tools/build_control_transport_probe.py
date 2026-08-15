#!/usr/bin/env python3
"""Build the 12-pair control-byte transport FONT and GPL JSON probe."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

try:
    from .build_font100_cjk_probe import HEADER, MAGIC, extract_glyph, sha256
    from .cjk_localization_pipeline import pair_for_id
    from .patch_dsun_cjk16_probe import ALGORITHMIC_TRIPLE_IDS, CONTROL_PAIR_IDS, PRINTABLE_TRIPLE_IDS, printable_triple_for_id
except ImportError:
    from build_font100_cjk_probe import HEADER, MAGIC, extract_glyph, sha256
    from cjk_localization_pipeline import pair_for_id
    from patch_dsun_cjk16_probe import ALGORITHMIC_TRIPLE_IDS, CONTROL_PAIR_IDS, PRINTABLE_TRIPLE_IDS, printable_triple_for_id


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT = ROOT / "scratch_test/font_16x15_experiment/FONT-100.zh-16x15.bin"
DEFAULT_JSON = ROOT / "scratch_test/font_16x15_experiment/GPL-2.current.json"
SOURCE_CODES = (0x40, 0x23, 0x24, 0x5B, 0x5D, 0x2A) * 2
TARGET_SUFFIX = "  CJK 16X15 TEST" + "." * 18


def build_extension(payload: bytes, ids: tuple[int, ...]) -> bytes:
    glyphs = [extract_glyph(payload, code) for code in SOURCE_CODES]
    if {height for _, height, _ in glyphs} != {15}:
        raise ValueError("control transport probe requires 15-pixel source glyphs")
    bank_count = max(ids) // 256 + 1
    grouped: dict[int, list[tuple[int, tuple[int, int, bytes]]]] = {}
    for cjk_id, glyph in zip(ids, glyphs):
        grouped.setdefault(cjk_id // 256, []).append((cjk_id & 0xFF, glyph))

    banks: list[bytes] = []
    for bank_id in range(bank_count):
        selected = grouped.get(bank_id, [])
        table = [0] * 256
        records = bytearray()
        cursor = 4 + 256 * 2
        fallback = cursor
        for index, (width, _, pixels) in selected:
            table[index] = cursor
            record = struct.pack("<H", width) + pixels
            records += record
            cursor += len(record)
        table = [value or fallback for value in table]
        banks.append(struct.pack("<HH", 256, 4) + struct.pack("<256H", *table) + records)

    directory_offset = HEADER.size
    cursor = directory_offset + bank_count * 2
    offsets: list[int] = []
    body = bytearray()
    for bank in banks:
        offsets.append(cursor)
        body += bank
        cursor += len(bank)
    if cursor > 0xFFFF:
        raise ValueError("probe extension does not fit the current single segment")
    return HEADER.pack(MAGIC, 2, bank_count, 15, 256, directory_offset) + struct.pack(
        f"<{bank_count}H", *offsets
    ) + body


def patch_json(document: dict[str, object], transport: str) -> tuple[dict[str, object], bytes, tuple[int, ...]]:
    if transport == "control-pair":
        ids = CONTROL_PAIR_IDS
        encoded = b"".join(pair_for_id(cjk_id) for cjk_id in ids)
        suffix = TARGET_SUFFIX
    elif transport == "printable-triple":
        ids = PRINTABLE_TRIPLE_IDS
        encoded = b"".join(printable_triple_for_id(cjk_id) for cjk_id in ids)
        suffix = "  CJK 16X15 TEST" + "." * 6
    else:
        ids = ALGORITHMIC_TRIPLE_IDS
        encoded = b"".join(printable_triple_for_id(cjk_id) for cjk_id in ids)
        suffix = "  CJK 16X15 TEST" + "." * 6
    probe_text = encoded.decode("ascii") + suffix
    matches = []
    for instruction in document.get("instructions", []):
        for parameter in instruction.get("params", []):
            for token in parameter:
                if token.get("kind") == "immediate_string" and "CJK 16X15 TEST" in token.get("value", ""):
                    matches.append(token)
    if len(matches) != 1:
        raise ValueError(f"expected one CJK probe string, found {len(matches)}")
    matches[0]["value"] = probe_text
    return document, encoded, ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--font-output", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument(
        "--transport",
        choices=("control-pair", "printable-triple", "algorithmic-triple"),
        default="control-pair",
    )
    args = parser.parse_args()

    payload = args.font.read_bytes()
    if MAGIC in payload:
        raise ValueError("source FONT already contains a CJK2 extension")
    if args.transport == "control-pair":
        ids = CONTROL_PAIR_IDS
    elif args.transport == "printable-triple":
        ids = PRINTABLE_TRIPLE_IDS
    else:
        ids = ALGORITHMIC_TRIPLE_IDS
    extension = build_extension(payload, ids)
    font_output = payload + extension
    args.font_output.write_bytes(font_output)
    document, pair_bytes, ids = patch_json(json.loads(args.json.read_text(encoding="utf-8")), args.transport)
    args.json_output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ids={','.join(map(str, ids))}")
    print(f"pairs={pair_bytes.hex(' ').upper()}")
    print(f"decoded_length={len(next(t['value'] for i in document['instructions'] for p in i.get('params', []) for t in p if t.get('kind') == 'immediate_string' and 'CJK 16X15 TEST' in t.get('value', '')))}")
    print(f"font_length={len(font_output)}")
    print(f"font_sha256={sha256(font_output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
