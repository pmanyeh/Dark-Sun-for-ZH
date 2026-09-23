#!/usr/bin/env python3
"""Compile the translated NAME-1 object-name table into a verified GPLDATA.GFF patch.

GPLDATA.GFF/NAME-1 is a fixed 25-byte x N-record table (see docs/re/re_41): each
record holds a NUL-terminated ASCII display name followed by leftover, unread
buffer bytes. Because every record has the same width, a translation is applied
as an in-place byte replacement -- no chunk-length change and no relocation of
any other record, unlike the variable-length SPIN and GPL importers.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from .cjk_localization_pipeline import (
        DEFAULT_MAPPING,
        encode_text,
        load_mapping,
        sha256,
        verify_extracted_gff_chunks,
        write_json,
    )
except ImportError:
    from cjk_localization_pipeline import (
        DEFAULT_MAPPING,
        encode_text,
        load_mapping,
        sha256,
        verify_extracted_gff_chunks,
        write_json,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME_DIR = ROOT / "from Steam/games/Dark Sun-ENG/GAME/DARKSUN"
DEFAULT_GPLDATA = DEFAULT_GAME_DIR / "GPLDATA.GFF"
DEFAULT_TRANSLATIONS = ROOT / "localization/NAME_objects_translated.json"
DEFAULT_OPEN_DS = ROOT / "vendor/opends/target/release"
DEFAULT_GFF_CAT = DEFAULT_OPEN_DS / "gff-cat.exe"

RECORD_BYTES = 25
NAME_KIND = "NAME"
NAME_CHUNK_ID = 1


def run(*arguments: Path | str) -> None:
    subprocess.run([str(item) for item in arguments], check=True)


def parse_records(chunk: bytes) -> list[bytes]:
    if len(chunk) % RECORD_BYTES != 0:
        raise ValueError(f"NAME-1 chunk is {len(chunk)} bytes, not a multiple of {RECORD_BYTES}")
    return [chunk[i : i + RECORD_BYTES] for i in range(0, len(chunk), RECORD_BYTES)]


def record_name(record: bytes) -> str:
    terminator = record.find(0)
    if terminator < 0:
        raise ValueError(f"fixed NAME-1 record has no NUL terminator: {record!r}")
    return record[:terminator].decode("ascii")


def build_patched_chunk(
    records: list[bytes], translations: dict[str, str], mapping: dict[str, object]
) -> tuple[bytes, list[dict[str, object]]]:
    """Rewrite each record's leading name in place; leave everything else untouched."""
    patched = bytearray()
    edits: list[dict[str, object]] = []
    for slot, record in enumerate(records):
        name = record_name(record)
        translation = translations.get(name) if name else None
        if not translation:
            patched += record
            continue
        encoded = encode_text(translation, mapping)
        if len(encoded) + 1 > RECORD_BYTES:
            raise ValueError(
                f"slot {slot} ({name!r} -> {translation!r}) encodes to {len(encoded)} bytes; "
                f"the fixed record only has {RECORD_BYTES - 1} usable bytes before the terminator"
            )
        new_record = bytes(encoded) + b"\x00" + record[len(encoded) + 1 :]
        if len(new_record) != RECORD_BYTES:
            raise ValueError(f"slot {slot}: rebuilt record is {len(new_record)} bytes, expected {RECORD_BYTES}")
        patched += new_record
        edits.append(
            {
                "slot": slot,
                "en": name,
                "zh": translation,
                "encoded_hex": encoded.hex(),
                "encoded_bytes": len(encoded),
            }
        )
    return bytes(patched), edits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_GPLDATA, help="GPLDATA.GFF to patch")
    parser.add_argument(
        "--baseline", type=Path, help="pristine GPLDATA.GFF used for the full-container proof (defaults to --source)"
    )
    parser.add_argument(
        "--prior-package",
        type=Path,
        help="an existing darksun-gpl-dialogue-patch package.json to layer this patch on top of",
    )
    parser.add_argument("--translations", type=Path, default=DEFAULT_TRANSLATIONS)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--gff-cat", type=Path, default=DEFAULT_GFF_CAT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")

    prior_package: dict[str, object] | None = None
    if args.prior_package:
        prior_package = json.loads(args.prior_package.read_text(encoding="utf-8"))
        if prior_package.get("format") != "darksun-gpl-dialogue-patch":
            raise ValueError(f"unsupported prior package: {args.prior_package}")
        source = args.prior_package.parent / str(prior_package["patched_file"])
        baseline = Path(str(prior_package["source"]))
        if sha256(baseline.read_bytes()) != prior_package["source_sha256"]:
            raise ValueError("prior package baseline GPLDATA.GFF does not match its own manifest")
    else:
        source = args.source.resolve()
        baseline = (args.baseline or args.source).resolve()

    mapping = load_mapping(args.mapping)
    translations_doc = json.loads(args.translations.read_text(encoding="utf-8"))
    translations = {entry["en"]: entry["zh"] for entry in translations_doc["entries"] if entry.get("zh")}

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="darksun-name-records-", dir=output.parent) as temporary:
        temporary_root = Path(temporary)
        staging = temporary_root / "package"
        staging.mkdir(parents=True)

        original_chunk_file = staging / "NAME-1.original.bin"
        run(args.gff_cat, "extract", source, NAME_KIND, str(NAME_CHUNK_ID), "-o", original_chunk_file)
        original_chunk = original_chunk_file.read_bytes()
        records = parse_records(original_chunk)
        blank_slots = [index for index, record in enumerate(records) if record == b"\x00" * RECORD_BYTES]

        patched_chunk, edits = build_patched_chunk(records, translations, mapping)
        if len(patched_chunk) != len(original_chunk):
            raise ValueError("patched NAME-1 chunk changed length; the fixed-record layout must be preserved")
        patched_chunk_file = staging / "NAME-1.bin"
        patched_chunk_file.write_bytes(patched_chunk)

        patched_gff = staging / "GPLDATA.GFF"
        run(args.gff_cat, "replace", source, NAME_KIND, str(NAME_CHUNK_ID), patched_chunk_file, "-o", patched_gff)

        name_record = {
            "kind": NAME_KIND,
            "chunk_id": NAME_CHUNK_ID,
            "source_bytes": len(original_chunk),
            "source_sha256": sha256(original_chunk),
            "encoded_byte_length": len(patched_chunk),
            "sha256": sha256(patched_chunk),
            "file": "NAME-1.bin",
        }

        target_records = list(prior_package["chunks"]) if prior_package else []
        target_records.append(name_record)
        edit_records = list(prior_package["edits"]) if prior_package else []
        edit_records.extend(edits)

        original_all = temporary_root / "original-all"
        patched_all = temporary_root / "patched-all"
        run(args.gff_cat, "extract", baseline, "--all", "-o", original_all)
        run(args.gff_cat, "extract", patched_gff, "--all", "-o", patched_all)
        # NAME-1 keeps its length, but a prior dialogue package may have
        # resized GPL (GFFI-8) and MAS (GFFI-7) chunks.
        verification = verify_extracted_gff_chunks(
            original_all, patched_all, target_records, {"GFFI-7.bin", "GFFI-8.bin"}
        )

        package = {
            "format": "darksun-gpl-dialogue-patch",
            "version": 1,
            "source": str(baseline),
            "source_sha256": sha256(baseline.read_bytes()),
            "patched_file": "GPLDATA.GFF",
            "patched_bytes": len(patched_gff.read_bytes()),
            "patched_sha256": sha256(patched_gff.read_bytes()),
            "name_records": {
                "record_bytes": RECORD_BYTES,
                "record_count": len(records),
                "blank_slots": blank_slots,
                "translated": len(edits),
            },
            "mapping_sha256": sha256(args.mapping.read_bytes()),
            "chunks": target_records,
            "edits": edit_records,
            "verification": verification,
        }
        for inherited_key in ("units", "withheld", "abi_constraint"):
            if prior_package and inherited_key in prior_package:
                package[inherited_key] = prior_package[inherited_key]
        write_json(staging / "gpl-dialogue-patch.json", package)
        shutil.move(str(staging), str(output))

    print(f"patched_gpldata={output / 'GPLDATA.GFF'}")
    print(f"patched_sha256={package['patched_sha256']}")
    print(f"name_records_translated={package['name_records']['translated']}")
    print(f"unchanged_chunks={verification['unchanged_non_target_chunks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
