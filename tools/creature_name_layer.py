#!/usr/bin/env python3
"""Chinese names for NPCs and monsters (SEGOBJEX.GFF, and saved region state).

Every creature in SEGOBJEX.GFF is an RDFF chunk whose header gives the
length of an object record at offset 6 (0x47, 0 or 1) and of the combat
record at offset 8 (always 0x3A); the combat record starts at offset 10.
v145 only matched the 0x47 form and missed 44 names (Slig among them). The name is the
combat record's 16-byte field at +0x28 (chunk offset 50..65); a 16-character
name has no NUL (the next field, ``04 00``, ends it). A Chinese name is at
most five characters (15 Base94 bytes) plus its NUL.

The engine copies the combat record into the runtime table [0x1665] (0x3A a
record) when a region loads, and saves write that table back: SAVE/5 holds
the current region and other SAVE chunks the regions already visited, as
back-to-back 0x3A records with the name at +0x28. Old saves keep English
names for those creatures until ``patch_save_records`` rewrites them.

Names come from localization/catalog/creature_names.csv; a row with an empty
translation (the four joinable characters, user decision 2026-09-26) stays
English. Only the name fields change, so chunk and file sizes stay the same.
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

try:
    from .cjk_localization_pipeline import encode_text
except ImportError:
    from cjk_localization_pipeline import encode_text

ROOT = Path(__file__).resolve().parents[1]
CREATURE_NAMES = ROOT / "localization/catalog/creature_names.csv"

RDFF_COMBAT_LENGTH = bytes.fromhex("3a00")  # at chunk offset 8
COMBAT_RECORD = 0x3A
NAME_OFFSET = 0x28
NAME_BYTES = 16
SEGOBJEX_NAME = 10 + NAME_OFFSET  # combat record starts at chunk offset 10


def load_creature_names(path: Path = CREATURE_NAMES) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {row["original"]: row["translation_zh_tw"] for row in csv.DictReader(stream)
                if row["translation_zh_tw"]}


def gff_chunks(gff_cat: Path, path: Path) -> list[tuple[str, int, int, int]]:
    """(kind, id, file offset, length) of every chunk, from ``gff-cat list``."""
    listing = subprocess.run([str(gff_cat), "list", str(path)], capture_output=True, text=True, check=True)
    chunks = []
    for line in listing.stdout.splitlines()[1:]:
        kind, chunk_id, offset, length = line.rsplit(None, 3)
        chunks.append((kind.strip().strip("'").strip(), int(chunk_id), int(offset), int(length)))
    return chunks


def name_field(field: bytes) -> str:
    return field.split(b"\0", 1)[0].decode("latin-1")


def encoded_name(chinese: str, mapping: dict[str, object]) -> bytes:
    encoded = encode_text(chinese, mapping)
    if len(encoded) >= NAME_BYTES:
        raise ValueError(f"{chinese!r} encodes to {len(encoded)} bytes; a creature name holds {NAME_BYTES - 1}")
    return encoded + bytes(NAME_BYTES - len(encoded))


def patch_segobjex(
    data: bytes, chunks: list[tuple[str, int, int, int]], names: dict[str, str], mapping: dict[str, object]
) -> tuple[bytes, list[tuple[int, int, str, str]]]:
    """Rewrite the name field of every creature chunk named in ``names``.

    Returns the patched file and (file offset, chunk id, English, Chinese) per field.
    """
    result = bytearray(data)
    changed = []
    for kind, chunk_id, offset, length in chunks:
        if kind != "RDFF" or length < 10 + COMBAT_RECORD:
            continue
        if data[offset + 8 : offset + 10] != RDFF_COMBAT_LENGTH:
            continue
        start = offset + SEGOBJEX_NAME
        english = name_field(data[start : start + NAME_BYTES])
        if english in names:
            result[start : start + NAME_BYTES] = encoded_name(names[english], mapping)
            changed.append((start, chunk_id, english, names[english]))
    return bytes(result), changed


def patch_save_records(
    data: bytes, chunks: list[tuple[str, int, int, int]], names: dict[str, str], mapping: dict[str, object]
) -> tuple[bytes, list[tuple[int, int, str, str]]]:
    """Rewrite creature names in the saved 0x3A combat-record tables.

    Returns the patched file and (file offset, chunk id, English, Chinese) per field.
    """
    result = bytearray(data)
    changed = []
    for kind, chunk_id, offset, length in chunks:
        if kind != "SAVE" or length == 0 or length % COMBAT_RECORD:
            continue
        for record in range(length // COMBAT_RECORD):
            start = offset + record * COMBAT_RECORD + NAME_OFFSET
            english = name_field(data[start : start + NAME_BYTES])
            if english in names:
                result[start : start + NAME_BYTES] = encoded_name(names[english], mapping)
                changed.append((start, chunk_id, english, names[english]))
    return bytes(result), changed


def changed_ranges_are_names(before: bytes, after: bytes, starts: list[int]) -> bool:
    """True when every differing byte lies inside a 16-byte name field."""
    allowed = {index for start in starts for index in range(start, start + NAME_BYTES)}
    return len(before) == len(after) and all(
        index in allowed for index, (a, b) in enumerate(zip(before, after)) if a != b
    )
