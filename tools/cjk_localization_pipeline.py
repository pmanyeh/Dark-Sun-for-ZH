#!/usr/bin/env python3
"""Build the stable Unicode inventory and banked glyph assets for DS1 Chinese.

The generated mapping is append-only: existing character IDs never move.  Glyph
banks are standalone files so no bank, and no u16 record offset, crosses 64 KiB.
They are build artifacts; the JSON mapping is the durable source of identity.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import subprocess
import struct
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "localization/catalog/localization_manifest.csv"
DEFAULT_MANIFEST_JSON = ROOT / "localization/catalog/localization_manifest.json"
DEFAULT_MAPPING = ROOT / "localization/cjk_mapping.json"
DEFAULT_GFF_CAT = ROOT / "vendor/opends/target/release/gff-cat.exe"
DEFAULT_RESOURCE_GFF = ROOT / "from Steam/games/Dark Sun-ENG/GAME/DARKSUN/RESOURCE.GFF"
MAPPING_FORMAT = "darksun-cjk-map"
MAPPING_VERSION = 1
BANK_MAGIC = b"CJB1"
BANK_HEADER = struct.Struct("<4sHHHHI")
BANK_ENTRY = struct.Struct("<HH")
BANK_CAPACITY = 256
MAX_U16 = 0xFFFF
ETEN_WIDTH = 16
ETEN_HEIGHT = 15
ETEN_STRIDE = 30
ETEN_HANZI_COUNT = 13094
ETEN_SYMBOL_COUNT = 408
ETEN_COMMON_COUNT = 5401

# Rejected two-byte control transport, retained only to reproduce re_23's
# negative probe.  Control leads are consumed before the renderer sees them.
PAIR_LEADS = bytes([1, 2, *range(4, 9), 11, 12, *range(14, 32), 127])
PAIR_TRAILS = bytes(value for value in range(1, 128) if value not in (3, ord("%")))
PAIR_CAPACITY = len(PAIR_LEADS) * len(PAIR_TRAILS)

# Runtime-proven printable transport: '^' plus two base-94 digits ('!'..'~').
# Literal '^' is forbidden by the importer; the source catalog contains none.
# ID 5795 encodes as '^^^' and is skipped because that repeated-prefix sequence
# destabilises the engine's line-boundary traversal.
TRIPLE_PREFIX = ord("^")
TRIPLE_BASE = 94
TRIPLE_DIGIT_MIN = 0x21
TRIPLE_RESERVED_ID = (TRIPLE_PREFIX - TRIPLE_DIGIT_MIN) * TRIPLE_BASE + (TRIPLE_PREFIX - TRIPLE_DIGIT_MIN)
TRIPLE_CAPACITY = TRIPLE_BASE * TRIPLE_BASE - 1


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mapping_fingerprint(document: dict[str, object]) -> str:
    """Hash only fields that determine glyph identity and bank placement."""
    projection = {
        "format": document.get("format"),
        "version": document.get("version"),
        "bank_capacity": document.get("bank_capacity", BANK_CAPACITY),
        "entries": [
            {
                "id": entry["id"],
                "character": entry["character"],
                "bank": entry.get("bank", entry["id"] // BANK_CAPACITY),
                "index": entry.get("index", entry["id"] % BANK_CAPACITY),
                "active": entry.get("active", True),
            }
            for entry in document["entries"]
        ],
    }
    encoded = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded)


def eten_raw_index(high: int, low: int) -> int:
    if not 0xA1 <= high <= 0xF9 or not (0x40 <= low <= 0x7E or 0xA1 <= low <= 0xFE):
        raise ValueError(f"invalid Big5 code {high:02X}{low:02X}")
    return (high - 0xA1) * 157 + ((low - 0x40) if low < 0x7F else (low - 0x62))


ETEN_LAST_SYMBOL = eten_raw_index(0xA3, 0xBF)
ETEN_BASE_A440 = eten_raw_index(0xA4, 0x40)
ETEN_LAST_COMMON = eten_raw_index(0xC6, 0x7E)
ETEN_BASE_C940 = eten_raw_index(0xC9, 0x40)


def eten_slot(character: str) -> tuple[str, int]:
    """Map one Unicode character to its ETEN 3.53 16x15 file and slot."""
    try:
        encoded = character.encode("big5")
    except UnicodeEncodeError as exc:
        raise ValueError(f"U+{ord(character):04X} is not representable in Big5") from exc
    if len(encoded) != 2:
        raise ValueError(f"U+{ord(character):04X} is not a two-byte ETEN glyph")
    raw = eten_raw_index(encoded[0], encoded[1])
    if raw <= ETEN_LAST_SYMBOL:
        return "spc", raw
    if raw < ETEN_BASE_A440:
        raise ValueError(f"U+{ord(character):04X} falls in the Big5 A3C0-A43F gap")
    if raw <= ETEN_LAST_COMMON:
        return "std", raw - ETEN_BASE_A440
    if raw < ETEN_BASE_C940:
        raise ValueError(f"U+{ord(character):04X} falls in the Big5 C680-C93F gap")
    index = ETEN_COMMON_COUNT + raw - ETEN_BASE_C940
    if index >= ETEN_HANZI_COUNT:
        raise ValueError(f"U+{ord(character):04X} is beyond STDFONT.15")
    return "std", index


def eten_rasterizer(std_path: Path, spc_path: Path, advance: int, shadow: bool = True):
    if advance < ETEN_WIDTH:
        raise ValueError("ETEN glyph advance must be at least 16")
    std = std_path.read_bytes()
    spc = spc_path.read_bytes()
    expected_std = ETEN_HANZI_COUNT * ETEN_STRIDE
    expected_spc = ETEN_SYMBOL_COUNT * ETEN_STRIDE
    if len(std) < expected_std:
        raise ValueError(f"{std_path}: {len(std)} bytes; expected at least {expected_std}")
    if len(spc) < expected_spc:
        raise ValueError(f"{spc_path}: {len(spc)} bytes; expected at least {expected_spc}")

    def render(character: str) -> tuple[int, bytes]:
        bank_name, index = eten_slot(character)
        bank = std if bank_name == "std" else spc
        glyph = bank[index * ETEN_STRIDE : (index + 1) * ETEN_STRIDE]
        pixels = bytearray(advance * ETEN_HEIGHT)
        foreground: set[tuple[int, int]] = set()
        for y in range(ETEN_HEIGHT):
            row = glyph[y * 2 : y * 2 + 2]
            for x in range(ETEN_WIDTH):
                if row[x // 8] & (1 << (7 - x % 8)):
                    foreground.add((x, y))
                    pixels[y * advance + x] = 0xFE
        if not foreground:
            raise ValueError(f"ETEN produced an empty glyph for U+{ord(character):04X}")
        if shadow:
            for x, y in foreground:
                sx, sy = x + 1, y + 1
                if sx < advance and sy < ETEN_HEIGHT and (sx, sy) not in foreground:
                    pixels[sy * advance + sx] = 0x14
        return advance, bytes(pixels)

    return render


def is_asset_character(character: str) -> bool:
    """Return true for non-ASCII visible characters that need a new glyph."""
    return ord(character) > 0x7F and not character.isspace() and not unicodedata.category(character).startswith("C")


def read_translations(paths: Iterable[Path], column: str) -> list[str]:
    texts: list[str] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None or column not in reader.fieldnames:
                raise ValueError(f"{path}: missing CSV column {column!r}")
            for row in reader:
                value = row.get(column, "")
                if value and value.strip():
                    texts.append(unicodedata.normalize("NFC", value))
    return texts


def make_inventory(texts: Iterable[str]) -> Counter[str]:
    return Counter(character for text in texts for character in text if is_asset_character(character))


def pair_for_id(cjk_id: int) -> bytes:
    """Encode the rejected control-byte probe (historical reproduction only)."""
    if not 0 <= cjk_id < PAIR_CAPACITY:
        raise ValueError(f"CJK ID {cjk_id} exceeds candidate pair capacity {PAIR_CAPACITY}")
    lead_index, trail_index = divmod(cjk_id, len(PAIR_TRAILS))
    return bytes((PAIR_LEADS[lead_index], PAIR_TRAILS[trail_index]))


def transport_for_id(cjk_id: int) -> bytes:
    if not 0 <= cjk_id < TRIPLE_BASE * TRIPLE_BASE or cjk_id == TRIPLE_RESERVED_ID:
        raise ValueError(f"CJK ID {cjk_id} is outside the printable-triple ID space")
    high, low = divmod(cjk_id, TRIPLE_BASE)
    return bytes((TRIPLE_PREFIX, TRIPLE_DIGIT_MIN + high, TRIPLE_DIGIT_MIN + low))


def next_transport_id(cjk_id: int) -> int:
    return cjk_id + 1 if cjk_id == TRIPLE_RESERVED_ID else cjk_id


def load_mapping(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"format": MAPPING_FORMAT, "version": MAPPING_VERSION, "entries": []}
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format") != MAPPING_FORMAT or document.get("version") != MAPPING_VERSION:
        raise ValueError(f"{path}: unsupported mapping format or version")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: entries must be a list")
    seen_characters: set[str] = set()
    seen_ids: set[int] = set()
    for entry in entries:
        character, cjk_id = entry.get("character"), entry.get("id")
        if not isinstance(character, str) or len(character) != 1 or not isinstance(cjk_id, int):
            raise ValueError(f"{path}: invalid mapping entry {entry!r}")
        if character in seen_characters or cjk_id in seen_ids or cjk_id < 0:
            raise ValueError(f"{path}: duplicate or negative mapping entry {entry!r}")
        transport_for_id(cjk_id)
        seen_characters.add(character)
        seen_ids.add(cjk_id)
    return document


def encode_text(text: str, document: dict[str, object]) -> bytes:
    """Encode one UTF-8 catalog value to the runtime-safe printable transport."""
    ids = {entry["character"]: entry["id"] for entry in document["entries"]}
    output = bytearray()
    for position, character in enumerate(unicodedata.normalize("NFC", text)):
        codepoint = ord(character)
        if codepoint == 0:
            raise ValueError(f"NUL is not allowed in catalog text at character {position}")
        if codepoint <= 0x7F:
            if codepoint == TRIPLE_PREFIX:
                raise ValueError(f"literal '^' is reserved at character {position}")
            output.append(codepoint)
        elif character in ids:
            output += transport_for_id(ids[character])
        else:
            raise ValueError(
                f"unmapped character {character!r} U+{codepoint:04X} at character {position}"
            )
    return bytes(output)


def insert_spin_title_newline(text: str) -> str:
    """Put the SPIN description on the line after its first title separator."""
    positions = [position for separator in ("：", ":") if (position := text.find(separator)) >= 0]
    if not positions:
        return text
    position = min(positions) + 1
    if text[position : position + 2] == "\r\n":
        return text
    return text[:position] + "\r\n" + text[position:].lstrip(" ")


def update_mapping(document: dict[str, object], inventory: Counter[str], sources: list[Path]) -> dict[str, object]:
    old_entries = document["entries"]
    by_character = {entry["character"]: entry for entry in old_entries}
    next_id = next_transport_id(max((entry["id"] for entry in old_entries), default=-1) + 1)
    for character in sorted(inventory, key=ord):
        if character not in by_character:
            by_character[character] = {"character": character, "id": next_id}
            next_id = next_transport_id(next_id + 1)
    entries: list[dict[str, object]] = []
    for entry in sorted(by_character.values(), key=lambda item: item["id"]):
        cjk_id = entry["id"]
        transport = transport_for_id(cjk_id)
        entries.append(
            {
                "id": cjk_id,
                "character": entry["character"],
                "unicode": f"U+{ord(entry['character']):04X}",
                "bank": cjk_id // BANK_CAPACITY,
                "index": cjk_id % BANK_CAPACITY,
                "transport_hex": transport.hex().upper(),
                "occurrences": inventory.get(entry["character"], 0),
                "active": entry["character"] in inventory,
            }
        )
    return {
        "format": MAPPING_FORMAT,
        "version": MAPPING_VERSION,
        "id_policy": "append-only; new characters sorted by Unicode code point",
        "bank_capacity": BANK_CAPACITY,
        "transport": {
            "kind": "printable-triple-base94",
            "status": "algorithmic base-94 resolver runtime verified",
            "prefix": "^",
            "digit_range_hex": ["21", "7E"],
            "literal_prefix_policy": "forbidden; importer raises an error",
            "reserved_sequence": "^^^",
            "reserved_id": TRIPLE_RESERVED_ID,
            "reserved_runtime_result": "single '?' replacement glyph",
            "capacity": TRIPLE_CAPACITY,
        },
        "sources": [str(path.resolve().relative_to(ROOT)) for path in sources],
        "active_character_count": len(inventory),
        "entry_count": len(entries),
        "entries": entries,
    }


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compile_gff_text_replacements(
    manifest: dict[str, object], document: dict[str, object], *, title_newline: bool = False
) -> tuple[dict[tuple[str, str, int], bytes], list[dict[str, object]], Counter[str]]:
    """Compile only whole SPIN chunks, preserving each catalogued terminator."""
    units = manifest.get("units")
    if not isinstance(units, list):
        raise ValueError("localization manifest must contain a units list")
    replacements: dict[tuple[str, str, int], bytes] = {}
    records: list[dict[str, object]] = []
    skipped: Counter[str] = Counter()
    for unit in units:
        translation = unit.get("translation_zh_tw", "")
        if not translation:
            continue
        category = unit.get("category")
        locations = unit.get("locations", [])
        if category != "spin":
            skipped[str(category)] += 1
            continue
        if not isinstance(locations, list) or not locations:
            raise ValueError(f"{unit.get('unit_id')}: translated SPIN unit has no locations")
        display_translation = insert_spin_title_newline(translation) if title_newline else translation
        encoded = encode_text(display_translation, document)
        for location in locations:
            terminator_name = location.get("terminator", "")
            if terminator_name not in ("", "CRLF") or "chunk_offset" in location:
                raise ValueError(
                    f"{unit.get('unit_id')}: SPIN location is not a supported whole chunk: {location!r}"
                )
            terminator = b"\r\n" if terminator_name == "CRLF" else b""
            payload = encoded + terminator
            container = location.get("container")
            kind = location.get("kind")
            chunk_id = location.get("chunk_id")
            if not isinstance(container, str) or not isinstance(kind, str) or not isinstance(chunk_id, int):
                raise ValueError(f"{unit.get('unit_id')}: invalid GFF location {location!r}")
            if kind.upper() != "SPIN":
                raise ValueError(f"{unit.get('unit_id')}: expected SPIN kind, found {kind!r}")
            try:
                expected_source_length = len(unit["original"].encode("ascii")) + len(terminator)
            except (KeyError, UnicodeEncodeError) as exc:
                raise ValueError(f"{unit.get('unit_id')}: SPIN original is missing or non-ASCII") from exc
            if location.get("length") != expected_source_length:
                raise ValueError(
                    f"{unit.get('unit_id')}: catalog length {location.get('length')} does not match "
                    f"original bytes plus {terminator_name or 'no'} terminator ({expected_source_length})"
                )
            key = (container, kind.upper(), chunk_id)
            previous = replacements.get(key)
            if previous is not None and previous != payload:
                raise ValueError(f"conflicting translations target {container}/{kind.upper()}-{chunk_id}")
            replacements[key] = payload
            records.append(
                {
                    "unit_id": unit.get("unit_id"),
                    "container": container,
                    "kind": kind.upper(),
                    "chunk_id": chunk_id,
                    "file": f"{container}/{kind.upper()}-{chunk_id}.txt",
                    "source_byte_length": expected_source_length,
                    "terminator": terminator_name,
                    "title_newline": title_newline and display_translation != translation,
                    "encoded_byte_length": len(payload),
                    "encoded_ascii": payload.decode("ascii"),
                    "encoded_base64": base64.b64encode(payload).decode("ascii"),
                    "sha256": sha256(payload),
                }
            )
    records.sort(key=lambda item: (item["container"], item["kind"], item["chunk_id"]))
    return replacements, records, skipped


def verify_extracted_gff_chunks(
    original_dir: Path,
    patched_dir: Path,
    records: list[dict[str, object]],
    allowed_metadata: set[str] | None = None,
) -> dict[str, object]:
    """Prove that target chunks match the package and all other payloads survive."""
    original = {path.name: path for path in original_dir.iterdir() if path.is_file()}
    patched = {path.name: path for path in patched_dir.iterdir() if path.is_file()}
    if original.keys() != patched.keys():
        missing = sorted(original.keys() - patched.keys())
        added = sorted(patched.keys() - original.keys())
        raise ValueError(f"repacked GFF chunk inventory differs; missing={missing[:10]}, added={added[:10]}")
    targets: dict[str, dict[str, object]] = {}
    for record in records:
        name = f"{record['kind']}-{record['chunk_id']}.bin"
        previous = targets.get(name)
        if previous is not None and previous["sha256"] != record["sha256"]:
            raise ValueError(f"replacement package has conflicting payloads for {name}")
        targets[name] = record
    missing_targets = sorted(targets.keys() - patched.keys())
    if missing_targets:
        raise ValueError(f"repacked GFF is missing replacement chunks: {missing_targets[:10]}")
    for name, record in targets.items():
        payload = patched[name].read_bytes()
        if sha256(payload) != record["sha256"] or len(payload) != record["encoded_byte_length"]:
            raise ValueError(f"repacked payload does not match replacement package: {name}")
    metadata = allowed_metadata if allowed_metadata is not None else {"GFFI-1.bin"}
    unexpected = []
    changed_targets = 0
    for name, path in original.items():
        changed = path.read_bytes() != patched[name].read_bytes()
        if changed and name in targets:
            changed_targets += 1
        elif changed and name not in metadata:
            unexpected.append(name)
    if unexpected:
        raise ValueError(f"non-target GFF chunks changed: {sorted(unexpected)[:10]}")
    return {
        "all_chunks": len(original),
        "target_chunks": len(targets),
        "changed_target_chunks": changed_targets,
        "unchanged_non_target_chunks": len(original) - len(targets) - len(metadata & original.keys()),
        "allowed_container_metadata": sorted(metadata & original.keys()),
    }


def rasterizer(
    font_path: Path,
    font_size: int,
    pixel_width: int,
    height: int,
    advance: int,
    threshold: int,
    fit_mode: str = "bbox-resize",
    add_shadow: bool = True,
    clamp_shadow_bottom: bool = False,
):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("glyph build requires Pillow") from exc
    font = ImageFont.truetype(str(font_path), font_size)

    def render(character: str) -> tuple[int, bytes]:
        left, top, right, bottom = font.getbbox(character)
        canvas = Image.new("L", (max(1, right - left), max(1, bottom - top)), 0)
        ImageDraw.Draw(canvas).text((-left, -top), character, font=font, fill=255)
        box = canvas.getbbox()
        if box is None:
            raise ValueError(f"font produced an empty glyph for U+{ord(character):04X}")
        glyph = canvas.crop(box)
        if fit_mode == "bbox-resize":
            glyph = glyph.resize((pixel_width, height), Image.Resampling.LANCZOS)
        elif fit_mode == "pixel-aligned":
            if glyph.width > pixel_width + 1 or glyph.height > height + 1:
                raise ValueError(
                    f"U+{ord(character):04X} is {glyph.width}x{glyph.height}, outside "
                    f"the {pixel_width}x{height} pixel-aligned canvas"
                )
            if glyph.width > pixel_width or glyph.height > height:
                left = max(0, (glyph.width - pixel_width) // 2)
                top = max(0, (glyph.height - height) // 2)
                glyph = glyph.crop(
                    (left, top, min(glyph.width, left + pixel_width), min(glyph.height, top + height))
                )
            aligned = Image.new("L", (pixel_width, height), 0)
            aligned.paste(glyph, ((pixel_width - glyph.width) // 2, (height - glyph.height) // 2))
            glyph = aligned
        else:
            raise ValueError(f"unknown glyph fit mode {fit_mode!r}")
        pixels = bytearray(advance * height)
        foreground: set[tuple[int, int]] = set()
        for y in range(height):
            for x in range(pixel_width):
                if glyph.getpixel((x, y)) >= threshold:
                    foreground.add((x, y))
                    pixels[y * advance + x] = 0xFE
        if add_shadow:
            for x, y in foreground:
                sx, sy = x + 1, y + 1
                if clamp_shadow_bottom and sy >= height:
                    sy = y
                if sx < advance and sy < height and (sx, sy) not in foreground:
                    pixels[sy * advance + sx] = 0x14
        return advance, bytes(pixels)

    return render


def build_bank(bank_id: int, entries: list[dict[str, object]], height: int, render) -> bytes:
    directory_offset = BANK_HEADER.size
    cursor = directory_offset + len(entries) * BANK_ENTRY.size
    directory = bytearray()
    records = bytearray()
    for entry in entries:
        width, pixels = render(entry["character"])
        record = struct.pack("<H", width) + pixels
        if cursor + len(record) > MAX_U16:
            raise ValueError(f"bank {bank_id} exceeds 64 KiB at CJK ID {entry['id']}")
        directory += BANK_ENTRY.pack(entry["index"], cursor)
        records += record
        cursor += len(record)
    header = BANK_HEADER.pack(BANK_MAGIC, 1, bank_id, height, len(entries), directory_offset)
    return header + directory + records


def read_bank(payload: bytes, expected_bank: int | None = None) -> dict[str, object]:
    """Validate a CJB1 payload and return its records keyed by bank-local index."""
    if len(payload) < BANK_HEADER.size:
        raise ValueError("CJB1 bank is shorter than its header")
    magic, version, bank_id, height, count, directory_offset = BANK_HEADER.unpack_from(payload)
    if magic != BANK_MAGIC or version != 1:
        raise ValueError("unsupported CJB1 magic or version")
    if expected_bank is not None and bank_id != expected_bank:
        raise ValueError(f"CJB1 bank id {bank_id} does not match expected {expected_bank}")
    directory_end = directory_offset + count * BANK_ENTRY.size
    if directory_offset < BANK_HEADER.size or directory_end > len(payload):
        raise ValueError("CJB1 directory is outside the bank payload")
    records: dict[int, bytes] = {}
    offsets: list[tuple[int, int]] = []
    for position in range(count):
        index, offset = BANK_ENTRY.unpack_from(payload, directory_offset + position * BANK_ENTRY.size)
        if index >= BANK_CAPACITY or index in records:
            raise ValueError(f"invalid or duplicate CJB1 index {index}")
        if offset < directory_end or offset + 2 > len(payload):
            raise ValueError(f"CJB1 record {index} offset is outside the payload")
        offsets.append((index, offset))
        records[index] = b""
    ordered = sorted(offsets, key=lambda item: item[1])
    for position, (index, offset) in enumerate(ordered):
        width = struct.unpack_from("<H", payload, offset)[0]
        end = offset + 2 + width * height
        next_offset = ordered[position + 1][1] if position + 1 < len(ordered) else len(payload)
        if end != next_offset:
            raise ValueError(f"CJB1 record {index} has an invalid size or overlapping offset")
        records[index] = payload[offset:end]
    return {"bank": bank_id, "height": height, "records": records}


def glyph_record_for_id(cjk_id: int, banks: dict[int, dict[str, object]]) -> bytes:
    bank_id, index = divmod(cjk_id, BANK_CAPACITY)
    bank = banks.get(bank_id)
    if bank is None:
        raise ValueError(f"missing CJB1 bank {bank_id} for CJK ID {cjk_id}")
    record = bank["records"].get(index)
    if record is None:
        raise ValueError(f"missing CJK ID {cjk_id} (bank {bank_id}, index {index})")
    return record


def command_inventory(args: argparse.Namespace) -> None:
    sources = [path.resolve() for path in args.catalog]
    inventory = make_inventory(read_translations(sources, args.column))
    document = update_mapping(load_mapping(args.mapping), inventory, sources)
    write_json(args.mapping, document)
    print(f"translations_with_text={sum(1 for _ in read_translations(sources, args.column))}")
    print(f"active_characters={len(inventory)}")
    print(f"mapping_entries={len(document['entries'])}")
    print(f"banks={(len(document['entries']) + BANK_CAPACITY - 1) // BANK_CAPACITY}")
    print(f"transport_capacity={TRIPLE_CAPACITY}")
    print(args.mapping)


def command_build(args: argparse.Namespace) -> None:
    document = load_mapping(args.mapping)
    entries = [entry for entry in document["entries"] if entry.get("active", True)]
    if args.eten_dir:
        std_path = args.eten_dir / "STDFONT.15"
        spc_path = args.eten_dir / "SPCFONT.15"
        render = eten_rasterizer(std_path, spc_path, args.advance, not args.no_shadow)
        source = {
            "kind": "eten-3.53-16x15",
            "std_file": std_path.name,
            "std_sha256": sha256(std_path.read_bytes()),
            "spc_file": spc_path.name,
            "spc_sha256": sha256(spc_path.read_bytes()),
            "shadow": not args.no_shadow,
        }
    else:
        render = rasterizer(
            args.font,
            args.font_size,
            args.pixel_width,
            args.height,
            args.advance,
            args.threshold,
            args.fit_mode,
            not args.no_shadow,
            args.clamp_shadow_bottom,
        )
        source = {
            "kind": "ttf-provisional",
            "file": args.font.name,
            "sha256": sha256(args.font.read_bytes()),
            "font_size": args.font_size,
            "pixel_width": args.pixel_width,
            "threshold": args.threshold,
            "fit_mode": args.fit_mode,
            "shadow": not args.no_shadow,
            "clamp_shadow_bottom": args.clamp_shadow_bottom,
        }
    args.output.mkdir(parents=True, exist_ok=True)
    bank_documents = []
    for bank_id in sorted({entry["bank"] for entry in entries}):
        bank_entries = [entry for entry in entries if entry["bank"] == bank_id]
        payload = build_bank(bank_id, bank_entries, args.height, render)
        path = args.output / f"cjk-bank-{bank_id:03d}.bin"
        path.write_bytes(payload)
        bank_documents.append({"bank": bank_id, "glyphs": len(bank_entries), "bytes": len(payload), "sha256": sha256(payload), "file": path.name})
        print(f"bank={bank_id} glyphs={len(bank_entries)} bytes={len(payload)} sha256={sha256(payload)}")
    package = {"format": "darksun-cjk-bank-set", "version": 1, "mapping_fingerprint": mapping_fingerprint(document), "mapping_sha256": sha256(args.mapping.read_bytes()), "glyph_height": args.height, "advance": args.advance, "glyph_source": source, "banks": bank_documents}
    write_json(args.output / "cjk-bank-set.json", package)
    print(args.output / "cjk-bank-set.json")


def command_encode(args: argparse.Namespace) -> None:
    document = load_mapping(args.mapping)
    output = encode_text(args.text, document)
    print(output.hex(" ").upper())


def command_compile_catalog(args: argparse.Namespace) -> None:
    document = load_mapping(args.mapping)
    units = []
    errors = []
    with args.catalog.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {args.id_column, args.column}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{args.catalog}: missing CSV columns {sorted(required)}")
        for row_number, row in enumerate(reader, 2):
            text = row.get(args.column, "")
            if not text:
                continue
            unit_id = row.get(args.id_column, "")
            try:
                payload = encode_text(text, document)
            except ValueError as exc:
                errors.append(f"{args.catalog}:{row_number} ({unit_id}): {exc}")
                continue
            units.append(
                {
                    "unit_id": unit_id,
                    "text": text,
                    "encoded_ascii": payload.decode("ascii"),
                    "encoded_base64": base64.b64encode(payload).decode("ascii"),
                    "byte_length": len(payload),
                }
            )
    if errors:
        preview = "\n".join(errors[:20])
        suffix = f"\n... and {len(errors) - 20} more" if len(errors) > 20 else ""
        raise ValueError(f"catalog encoding failed with {len(errors)} error(s):\n{preview}{suffix}")
    package = {
        "format": "darksun-cjk-encoded-catalog",
        "version": 1,
        "catalog": str(args.catalog.resolve().relative_to(ROOT)),
        "catalog_sha256": sha256(args.catalog.read_bytes()),
        "mapping_sha256": sha256(args.mapping.read_bytes()),
        "column": args.column,
        "unit_count": len(units),
        "units": units,
    }
    write_json(args.output, package)
    print(f"encoded_units={len(units)}")
    print(args.output)


def command_compile_gff_text(args: argparse.Namespace) -> None:
    document = load_mapping(args.mapping)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    replacements, records, skipped = compile_gff_text_replacements(
        manifest, document, title_newline=args.title_newline
    )
    for (container, kind, chunk_id), payload in replacements.items():
        path = args.output / container / f"{kind}-{chunk_id}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    package = {
        "format": "darksun-gff-text-replacements",
        "version": 1,
        "scope": "whole SPIN chunks with catalogued terminators preserved",
        "display_policy": {
            "title_newline": args.title_newline,
            "separator": "first fullwidth or ASCII colon",
            "newline_bytes": "CRLF",
        },
        "manifest": str(args.manifest.resolve().relative_to(ROOT)),
        "manifest_sha256": sha256(args.manifest.read_bytes()),
        "mapping_sha256": sha256(args.mapping.read_bytes()),
        "replacement_count": len(replacements),
        "unit_location_count": len(records),
        "skipped_translated_units": dict(sorted(skipped.items())),
        "replacements": records,
    }
    write_json(args.output / "gff-text-replacements.json", package)
    print(f"replacement_chunks={len(replacements)}")
    print(f"replacement_locations={len(records)}")
    print("skipped_translated_units=" + ",".join(f"{key}:{value}" for key, value in sorted(skipped.items())))
    print(args.output / "gff-text-replacements.json")


def command_pack_gff_text(args: argparse.Namespace) -> None:
    if args.source.resolve() == args.output.resolve():
        raise ValueError("source and output GFF paths must differ")
    package = json.loads(args.package.read_text(encoding="utf-8"))
    if package.get("format") != "darksun-gff-text-replacements" or package.get("version") != 1:
        raise ValueError(f"{args.package}: unsupported replacement package")
    records = [item for item in package.get("replacements", []) if item.get("container") == args.source.name]
    if not records:
        raise ValueError(f"replacement package has no entries for {args.source.name}")
    replacement_dir = args.package.parent / args.source.name
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(args.gff_cat), "pack-text", str(args.source), str(replacement_dir), "-o", str(args.output)],
        check=True,
    )
    with tempfile.TemporaryDirectory(prefix="darksun-gff-verify-") as temporary:
        root = Path(temporary)
        original_dir, patched_dir = root / "original", root / "patched"
        subprocess.run(
            [str(args.gff_cat), "extract", str(args.source), "--all", "-o", str(original_dir)],
            check=True,
        )
        subprocess.run(
            [str(args.gff_cat), "extract", str(args.output), "--all", "-o", str(patched_dir)],
            check=True,
        )
        verification = verify_extracted_gff_chunks(original_dir, patched_dir, records)
    result = {
        "format": "darksun-gff-pack-verification",
        "version": 1,
        "source": str(args.source),
        "source_bytes": args.source.stat().st_size,
        "source_sha256": sha256(args.source.read_bytes()),
        "replacement_package": str(args.package),
        "replacement_package_sha256": sha256(args.package.read_bytes()),
        "output": str(args.output),
        "output_bytes": args.output.stat().st_size,
        "output_sha256": sha256(args.output.read_bytes()),
        **verification,
    }
    verification_path = args.output.with_suffix(args.output.suffix + ".verification.json")
    write_json(verification_path, result)
    for key in ("all_chunks", "target_chunks", "changed_target_chunks", "unchanged_non_target_chunks"):
        print(f"{key}={result[key]}")
    print(f"output_sha256={result['output_sha256']}")
    print(verification_path)


def command_verify_banks(args: argparse.Namespace) -> None:
    mapping = load_mapping(args.mapping)
    package = json.loads(args.package.read_text(encoding="utf-8"))
    if package.get("format") != "darksun-cjk-bank-set" or package.get("version") != 1:
        raise ValueError(f"{args.package}: unsupported bank-set format or version")
    if package.get("mapping_fingerprint") != mapping_fingerprint(mapping):
        raise ValueError("bank set was built from a different mapping")
    banks: dict[int, dict[str, object]] = {}
    for item in package.get("banks", []):
        bank_id = item["bank"]
        path = args.package.parent / item["file"]
        payload = path.read_bytes()
        if len(payload) != item["bytes"] or sha256(payload) != item["sha256"]:
            raise ValueError(f"{path}: size or SHA-256 does not match the bank set")
        bank = read_bank(payload, bank_id)
        if len(bank["records"]) != item["glyphs"]:
            raise ValueError(f"{path}: glyph count does not match the bank set")
        banks[bank_id] = bank
    checked = 0
    for entry in mapping["entries"]:
        if entry.get("active", True):
            glyph_record_for_id(entry["id"], banks)
            checked += 1
    print(f"verified_banks={len(banks)}")
    print(f"verified_glyphs={checked}")
    print("max_record_bytes=" + str(max(len(record) for bank in banks.values() for record in bank["records"].values())))


def command_audit_eten(args: argparse.Namespace) -> None:
    mapping = load_mapping(args.mapping)
    counts = Counter()
    errors = []
    for entry in mapping["entries"]:
        if not entry.get("active", True):
            continue
        try:
            bank, _ = eten_slot(entry["character"])
            counts[bank] += 1
        except ValueError as exc:
            errors.append(f"ID {entry['id']} {entry['unicode']}: {exc}")
    print(f"active_glyphs={sum(counts.values()) + len(errors)}")
    print(f"eten_std={counts['std']}")
    print(f"eten_spc={counts['spc']}")
    print(f"eten_missing={len(errors)}")
    if errors:
        raise ValueError("ETEN coverage gaps:\n" + "\n".join(errors))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--catalog", type=Path, action="append", default=[])
    inventory.add_argument("--column", default="translation_zh_tw")
    inventory.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    inventory.set_defaults(func=command_inventory)
    build = commands.add_parser("build-banks")
    build.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    build.add_argument("--output", type=Path, required=True)
    source = build.add_mutually_exclusive_group(required=True)
    source.add_argument("--font", type=Path)
    source.add_argument("--eten-dir", type=Path, help="directory containing STDFONT.15 and SPCFONT.15")
    build.add_argument("--font-size", type=int, default=16)
    build.add_argument("--pixel-width", type=int, default=15)
    build.add_argument("--height", type=int, default=15)
    build.add_argument("--advance", type=int, default=16)
    build.add_argument("--threshold", type=int, default=100)
    build.add_argument("--fit-mode", choices=("bbox-resize", "pixel-aligned"), default="bbox-resize")
    build.add_argument("--no-shadow", action="store_true", help="do not add the Dark Sun 0x14 drop shadow to ETEN glyphs")
    build.add_argument(
        "--clamp-shadow-bottom",
        action="store_true",
        help="keep a diagonal TTF shadow inside the last row by shifting it right only",
    )
    build.set_defaults(func=command_build)
    encode = commands.add_parser("encode")
    encode.add_argument("text")
    encode.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    encode.set_defaults(func=command_encode)
    compile_catalog = commands.add_parser("compile-catalog")
    compile_catalog.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    compile_catalog.add_argument("--column", default="translation_zh_tw")
    compile_catalog.add_argument("--id-column", default="unit_id")
    compile_catalog.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    compile_catalog.add_argument("--output", type=Path, required=True)
    compile_catalog.set_defaults(func=command_compile_catalog)
    compile_gff = commands.add_parser(
        "compile-gff-text", help="compile safe whole-chunk SPIN translations for gff-cat"
    )
    compile_gff.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_JSON)
    compile_gff.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    compile_gff.add_argument("--output", type=Path, required=True)
    compile_gff.add_argument(
        "--title-newline",
        action="store_true",
        help="insert CRLF after the first spell-name colon",
    )
    compile_gff.set_defaults(func=command_compile_gff_text)
    pack_gff = commands.add_parser(
        "pack-gff-text", help="pack a GFF replacement package and verify every extracted chunk"
    )
    pack_gff.add_argument("--source", type=Path, default=DEFAULT_RESOURCE_GFF)
    pack_gff.add_argument("--package", type=Path, required=True)
    pack_gff.add_argument("--gff-cat", type=Path, default=DEFAULT_GFF_CAT)
    pack_gff.add_argument("--output", type=Path, required=True)
    pack_gff.set_defaults(func=command_pack_gff_text)
    verify_banks = commands.add_parser("verify-banks")
    verify_banks.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    verify_banks.add_argument("--package", type=Path, required=True)
    verify_banks.set_defaults(func=command_verify_banks)
    audit_eten = commands.add_parser("audit-eten", help="check mapping coverage without requiring font files")
    audit_eten.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    audit_eten.set_defaults(func=command_audit_eten)
    return result


def main() -> int:
    args = parser().parse_args()
    if hasattr(args, "catalog") and not args.catalog:
        args.catalog = [DEFAULT_CATALOG]
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
