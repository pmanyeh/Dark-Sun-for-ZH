#!/usr/bin/env python3
"""Stage the four formal CJB1 banks and a FONT-100 scratch record probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from cjk_localization_pipeline import glyph_record_for_id, read_bank
from cjk_localization_pipeline import transport_for_id

ROOT = Path(__file__).resolve().parents[1]
LEGACY_FONT_LENGTH = 0x3640
SCRATCH_RECORD_SIZE = 242


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--bank-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gpl-json", type=Path)
    args = parser.parse_args()
    font = args.font.read_bytes()
    if len(font) != LEGACY_FONT_LENGTH:
        raise ValueError(f"FONT payload must be exactly 0x{LEGACY_FONT_LENGTH:04X} bytes")
    package = json.loads(args.bank_package.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    banks = {}
    staged = []
    for item in package["banks"]:
        source = args.bank_package.parent / item["file"]
        payload = source.read_bytes()
        bank_id = item["bank"]
        banks[bank_id] = read_bank(payload, bank_id)
        target = args.output / f"C{bank_id}.BIN"
        shutil.copyfile(source, target)
        staged.append({"bank": bank_id, "file": target.name, "bytes": len(payload), "sha256": sha256(payload)})
    # Seed the scratch slot with ID 255. Runtime ID 256 must overwrite it,
    # making a cross-bank copy visually and byte-wise distinguishable.
    scratch = glyph_record_for_id(255, banks)
    if len(scratch) != SCRATCH_RECORD_SIZE:
        raise ValueError(f"scratch record must be {SCRATCH_RECORD_SIZE} bytes")
    font_output = args.output / "FONT-100.scratch.bin"
    font_output.write_bytes(font + scratch)
    manifest = {
        "format": "darksun-cjk-scratch-probe",
        "version": 1,
        "scratch_offset": LEGACY_FONT_LENGTH,
        "scratch_bytes": len(scratch),
        "scratch_seed_id": 255,
        "font_file": font_output.name,
        "font_sha256": sha256(font_output.read_bytes()),
        "banks": staged,
    }
    (args.output / "scratch-probe.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if args.gpl_json:
        document = json.loads(args.gpl_json.read_text(encoding="utf-8"))
        encoded = transport_for_id(255) + transport_for_id(256)
        probe = encoded.decode("ascii") + "  SCRATCH BANK 0-1 TEST" + "." * 26
        matches = [
            token
            for instruction in document.get("instructions", [])
            for parameter in instruction.get("params", [])
            for token in parameter
            if token.get("kind") == "immediate_string" and "CJK 16X15 TEST" in token.get("value", "")
        ]
        if len(matches) != 1:
            raise ValueError(f"expected one CJK probe string, found {len(matches)}")
        matches[0]["value"] = probe
        json_output = args.output / "GPL-2.scratch.json"
        json_output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"probe_ids=255,256")
        print(f"probe_transport={encoded.hex(' ').upper()}")
        print(json_output)
    print(f"staged_banks={len(staged)}")
    print(f"scratch_offset=0x{LEGACY_FONT_LENGTH:04X}")
    print(f"scratch_bytes={len(scratch)}")
    print(font_output)


if __name__ == "__main__":
    main()
