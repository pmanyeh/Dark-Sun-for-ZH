"""Build translation catalogs from OpenDS output and Dark Sun resources.

The source game files are read-only. Generated catalogs retain every GPL/MAS
string occurrence while deduplicating exact source strings into translation
units. GFF text resources and conservative NUL-terminated DSUN.EXE strings are
then merged into one localization manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


TEXT_KINDS = {"SPIN", "TEXT", "MERR", "ETME"}
GFF_FILES = (
    "GPLDATA.GFF",
    "RESOURCE.GFF",
    "CINE.GFF",
    "DARKRUN.GFF",
    "DARKSAVE.GFF",
    "CHARSAVE.GFF",
    "BACKSAVE.GFF",
)


def stable_id(prefix: str, namespace: str, text: str) -> str:
    digest = hashlib.sha1(f"{namespace}\0{text}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_json(args: list[str]) -> Any:
    completed = subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(completed.stdout)


def read_chunk(gff_cat: Path, gff: Path, kind: str, chunk_id: int) -> bytes:
    completed = subprocess.run(
        [str(gff_cat), "extract", str(gff), kind, str(chunk_id)],
        check=True,
        capture_output=True,
    )
    return completed.stdout


def whitespace_metadata(text: str) -> dict[str, int]:
    return {
        "leading_spaces": len(text) - len(text.lstrip(" ")),
        "trailing_spaces": len(text) - len(text.rstrip(" ")),
    }


def build_dialogue(dialog_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    data = json.loads(dialog_path.read_text(encoding="utf-8"))
    units: OrderedDict[str, dict[str, Any]] = OrderedDict()
    occurrences: list[dict[str, Any]] = []

    for chunk in data["chunks"]:
        for string in chunk.get("strings", []):
            occurrence_id = f"DLOC_{len(occurrences) + 1:05d}"
            value = string.get("value")
            unit_id = stable_id("DLG", "dialogue", value) if value is not None else None
            occurrence = {
                "occurrence_id": occurrence_id,
                "unit_id": unit_id,
                "chunk": chunk["chunk"],
                "kind": chunk["kind"],
                "chunk_id": chunk["id"],
                "offset": string["offset"],
                "offset_hex": f"0x{string['offset']:04X}",
                "opcode": string["opcode"],
                "opcode_hex": f"0x{string['opcode']:02X}",
                "opcode_name": string.get("opcode_name"),
                "source": string.get("source"),
                "sub_type": string.get("sub_type"),
                "text_id": string.get("text_id"),
                "unresolved": bool(string.get("unresolved", False)),
            }
            if value is None:
                occurrence["possible_writers"] = string.get("possible_writers", [])
                occurrence["possible_writers_filter"] = string.get("possible_writers_filter")
            occurrences.append(occurrence)

            if value is None:
                continue
            if unit_id not in units:
                is_placeholder = bool(re.fullmatch(r"<[^>]+>", value.strip()))
                units[unit_id] = {
                    "unit_id": unit_id,
                    "category": "dialogue",
                    "original": value,
                    "translation_zh_tw": "",
                    "status": "not_translatable" if is_placeholder else "pending",
                    "translate": not is_placeholder,
                    "whitespace": whitespace_metadata(value),
                    "occurrence_ids": [],
                }
            units[unit_id]["occurrence_ids"].append(occurrence_id)

    result_units = list(units.values())
    summary = {
        "source_records": data["string_count"],
        "occurrences": len(occurrences),
        "resolved_occurrences": sum(o["unit_id"] is not None for o in occurrences),
        "unresolved_occurrences": sum(o["unit_id"] is None for o in occurrences),
        "unique_units": len(result_units),
        "translatable_units": sum(u["translate"] for u in result_units),
        "chunks": data["chunk_count"],
        "lstr_stats": data.get("lstr_stats", {}),
    }
    return result_units, occurrences, summary


def decode_text_chunk(raw: bytes) -> tuple[str, str]:
    terminator = ""
    if raw.endswith(b"\r\n"):
        raw, terminator = raw[:-2], "CRLF"
    elif raw.endswith(b"\n"):
        raw, terminator = raw[:-1], "LF"
    elif raw.endswith(b"\x00"):
        raw, terminator = raw[:-1], "NUL"
    return raw.decode("cp437"), terminator


def load_existing_translations(project_root: Path) -> tuple[dict[int, str], list[dict[str, Any]]]:
    spin_data = json.loads((project_root / "localization/SPIN_spells_translated.json").read_text(encoding="utf-8"))
    name_data = json.loads((project_root / "localization/NAME_objects_translated.json").read_text(encoding="utf-8"))
    spin = {int(entry["id"]): entry.get("zh", "") for entry in spin_data["entries"]}
    return spin, name_data["entries"]


def add_resource_unit(
    units: OrderedDict[str, dict[str, Any]],
    namespace: str,
    category: str,
    text: str,
    location: dict[str, Any],
    translation: str = "",
    translate: bool = True,
    notes: str = "",
) -> None:
    unit_id = stable_id("LOC", namespace, text)
    if unit_id not in units:
        units[unit_id] = {
            "unit_id": unit_id,
            "category": category,
            "original": text,
            "translation_zh_tw": translation,
            "status": "translated_unreviewed" if translation else ("pending" if translate else "not_player_facing"),
            "translate": translate,
            "notes": notes,
            "locations": [],
        }
    elif translation and not units[unit_id]["translation_zh_tw"]:
        units[unit_id]["translation_zh_tw"] = translation
        units[unit_id]["status"] = "translated_unreviewed"
    units[unit_id]["locations"].append(location)


def extract_gff_resources(project_root: Path, game_dir: Path, gff_cat: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    spin_translations, name_entries = load_existing_translations(project_root)
    units: OrderedDict[str, dict[str, Any]] = OrderedDict()
    kind_counts: Counter[str] = Counter()

    for filename in GFF_FILES:
        gff = game_dir / filename
        rows = run_json([str(gff_cat), "list", str(gff), "--json"])
        for row in rows:
            kind = row["kind"]
            if kind not in TEXT_KINDS:
                continue
            raw = read_chunk(gff_cat, gff, kind, int(row["id"]))
            text, terminator = decode_text_chunk(raw)
            location = {
                "container": filename,
                "kind": kind,
                "chunk_id": row["id"],
                "file_offset": row["location"],
                "file_offset_hex": f"0x{row['location']:X}",
                "length": row["length"],
                "terminator": terminator,
            }
            translation = spin_translations.get(int(row["id"]), "") if kind == "SPIN" else ""
            translate = kind != "ETME"
            note = "Build/import metadata; extracted for completeness, not normally shown to players." if kind == "ETME" else ""
            add_resource_unit(units, f"gff:{kind}", kind.lower(), text, location, translation, translate, note)
            kind_counts[kind] += 1

    # NAME-1 is a composite binary table. Reuse the established 328-entry
    # extraction, but independently relocate every string in source order.
    gff = game_dir / "GPLDATA.GFF"
    rows = run_json([str(gff_cat), "list", str(gff), "--json"])
    name_row = next(row for row in rows if row["kind"] == "NAME" and int(row["id"]) == 1)
    raw_name = read_chunk(gff_cat, gff, "NAME", 1)
    cursor = 0
    for entry in name_entries:
        encoded = entry["en"].encode("ascii")
        internal_offset = raw_name.find(encoded, cursor)
        if internal_offset < 0:
            raise ValueError(f"Unable to relocate NAME id {entry['id']}: {entry['en']!r}")
        cursor = internal_offset + len(encoded)
        location = {
            "container": "GPLDATA.GFF",
            "kind": "NAME",
            "chunk_id": 1,
            "record_id": entry["id"],
            "chunk_offset": internal_offset,
            "chunk_offset_hex": f"0x{internal_offset:X}",
            "file_offset": name_row["location"] + internal_offset,
            "file_offset_hex": f"0x{name_row['location'] + internal_offset:X}",
            "length": len(encoded),
        }
        add_resource_unit(
            units,
            "gff:NAME",
            "name",
            entry["en"],
            location,
            entry.get("zh", ""),
            True,
            entry.get("note", ""),
        )
        kind_counts["NAME"] += 1

    return list(units.values()), dict(sorted(kind_counts.items()))


EXE_STRING_RE = re.compile(rb"[\x09\x0A\x0D\x20-\x7E]{4,}\x00")


def classify_exe_string(text: str) -> tuple[str, bool]:
    lower = text.lower()
    if any(token in lower for token in (".c:", ".cpp:", "assert", "runtime overlay", "out of memory", "fatal", "error")):
        return "exe_diagnostic", True
    if "%" in text:
        return "exe_format_or_ui", True
    if text.isupper() or any(ch in text for ch in "!?…"):
        return "exe_ui_candidate", True
    return "exe_string_candidate", True


def plausible_exe_text(text: str) -> bool:
    """Conservatively reject printable machine-code accidents."""
    flat = " ".join(text.replace("\r", " ").replace("\n", " ").replace("\t", " ").split())
    if not flat or re.search(r"(.)\1{3,}", flat):
        return False
    letters = [ch for ch in flat if ch.isalpha()]
    if len(letters) < 2:
        return False
    words = re.findall(r"[A-Za-z]+", flat)
    has_space = " " in flat
    if not has_space:
        # Standalone UI labels in this executable are overwhelmingly uppercase
        # (CANCEL, OPEN, INFO) or conventional title-case identifiers.
        return flat.isupper() or flat.istitle()
    vowels = sum(ch.lower() in "aeiouy" for ch in letters)
    if vowels / len(letters) < 0.15:
        return False
    return any(len(word) >= 3 for word in words)


def extract_exe_strings(exe_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    data = exe_path.read_bytes()
    units: OrderedDict[str, dict[str, Any]] = OrderedDict()
    rejected = 0
    occurrences = 0
    for match in EXE_STRING_RE.finditer(data):
        raw = match.group()[:-1]
        text = raw.decode("ascii")
        flat = text.replace("\r", " ").replace("\n", " ").replace("\t", " ").strip()
        if len(flat) > 500 or not plausible_exe_text(text):
            rejected += 1
            continue
        # Reject obvious machine-code accidents: translation candidates need a
        # plausible ratio of letters, spaces, punctuation, or format markers.
        plausible = sum(ch.isalnum() or ch.isspace() or ch in ".,!?;:'\"-_/()[]%+*=<>\\" for ch in flat)
        if plausible / len(flat) < 0.85:
            rejected += 1
            continue
        category, translate = classify_exe_string(text)
        location = {
            "container": "DSUN.EXE",
            "file_offset": match.start(),
            "file_offset_hex": f"0x{match.start():X}",
            "length": len(raw),
        }
        add_resource_unit(
            units,
            f"exe:{category}",
            category,
            text,
            location,
            "",
            False,
            "Heuristic NUL-terminated ASCII candidate; review in-game visibility before translation.",
        )
        unit_id = stable_id("LOC", f"exe:{category}", text)
        units[unit_id]["status"] = "needs_review"
        occurrences += 1
    return list(units.values()), {"occurrences": occurrences, "unique_units": len(units), "rejected_runs": rejected}


def write_dialogue_csv(path: Path, units: list[dict[str, Any]], occurrence_lookup: dict[str, dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "unit_id", "original", "translation_zh_tw", "status", "translate",
            "occurrence_count", "first_location", "leading_spaces", "trailing_spaces",
        ])
        writer.writeheader()
        for unit in units:
            first = occurrence_lookup[unit["occurrence_ids"][0]]
            writer.writerow({
                "unit_id": unit["unit_id"],
                "original": unit["original"],
                "translation_zh_tw": unit["translation_zh_tw"],
                "status": unit["status"],
                "translate": unit["translate"],
                "occurrence_count": len(unit["occurrence_ids"]),
                "first_location": f"{first['chunk']}@{first['offset_hex']}",
                "leading_spaces": unit["whitespace"]["leading_spaces"],
                "trailing_spaces": unit["whitespace"]["trailing_spaces"],
            })


def write_occurrence_csv(path: Path, occurrences: list[dict[str, Any]]) -> None:
    fields = ["occurrence_id", "unit_id", "chunk", "kind", "chunk_id", "offset", "offset_hex", "opcode_hex", "opcode_name", "source", "sub_type", "text_id", "unresolved"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(occurrences)


def write_manifest_csv(path: Path, units: list[dict[str, Any]]) -> None:
    fields = ["unit_id", "category", "original", "translation_zh_tw", "status", "translate", "location_count", "notes"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for unit in units:
            writer.writerow({
                "unit_id": unit["unit_id"],
                "category": unit["category"],
                "original": unit["original"],
                "translation_zh_tw": unit["translation_zh_tw"],
                "status": unit["status"],
                "translate": unit["translate"],
                "location_count": len(unit.get("locations", unit.get("occurrence_ids", []))),
                "notes": unit.get("notes", ""),
            })


def preserve_existing_work(output_dir: Path, units: list[dict[str, Any]]) -> None:
    """Carry translations forward when regenerating catalogs.

    The unified CSV is loaded first and the dialogue-specific CSV second, so a
    translator working in dialogue_units.csv gets the final say for dialogue.
    Blank cells do not erase an existing translation supplied by the curated
    SPIN/NAME dictionaries.
    """
    by_id = {unit["unit_id"]: unit for unit in units}
    for filename in ("localization_manifest.csv", "dialogue_units.csv"):
        path = output_dir / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                unit = by_id.get(row.get("unit_id", ""))
                translation = row.get("translation_zh_tw", "")
                if not unit or not translation:
                    continue
                unit["translation_zh_tw"] = translation
                unit["status"] = row.get("status") or "translated_unreviewed"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--game-dir", type=Path)
    parser.add_argument("--dialog-json", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    root = args.project_root.resolve()
    game_dir = (args.game_dir or root / "from Steam/games/Dark Sun-ENG/GAME/DARKSUN").resolve()
    dialog_json = (args.dialog_json or root / "localization/opends/ds1-dialog.json").resolve()
    output_dir = (args.output_dir or root / "localization/catalog").resolve()
    gff_cat = root / "vendor/opends/target/release/gff-cat.exe"
    for required in (dialog_json, gff_cat, game_dir / "DSUN.EXE"):
        if not required.exists():
            raise FileNotFoundError(required)
    output_dir.mkdir(parents=True, exist_ok=True)

    dialogue_units, dialogue_occurrences, dialogue_summary = build_dialogue(dialog_json)
    gff_units, gff_counts = extract_gff_resources(root, game_dir, gff_cat)
    exe_units, exe_summary = extract_exe_strings(game_dir / "DSUN.EXE")
    manifest_units = dialogue_units + gff_units + exe_units
    preserve_existing_work(output_dir, manifest_units)

    occurrence_lookup = {o["occurrence_id"]: o for o in dialogue_occurrences}
    dialogue_document = {"schema_version": 1, "summary": dialogue_summary, "units": dialogue_units}
    occurrence_document = {"schema_version": 1, "summary": {"count": len(dialogue_occurrences)}, "occurrences": dialogue_occurrences}
    category_counts = Counter(unit["category"] for unit in manifest_units)
    manifest_summary = {
        "unit_count": len(manifest_units),
        "translatable_unit_count": sum(unit["translate"] for unit in manifest_units),
        "translated_unreviewed_count": sum(bool(unit.get("translation_zh_tw")) for unit in manifest_units),
        "category_counts": dict(sorted(category_counts.items())),
        "dialogue": dialogue_summary,
        "gff_resource_occurrences": gff_counts,
        "exe": exe_summary,
    }
    source_hashes = {}
    for filename in ("GPLDATA.GFF", "RESOURCE.GFF", "CINE.GFF", "DARKRUN.GFF", "DARKSAVE.GFF", "CHARSAVE.GFF", "BACKSAVE.GFF", "DSUN.EXE"):
        source = game_dir / filename
        source_hashes[filename] = hashlib.sha256(source.read_bytes()).hexdigest().upper()
    manifest = {
        "schema_version": 1,
        "description": "Dark Sun: Shattered Lands unified Traditional Chinese localization manifest.",
        "source_game": "Steam English edition",
        "source_sha256": source_hashes,
        "summary": manifest_summary,
        "units": manifest_units,
    }

    dump_json(output_dir / "dialogue_units.json", dialogue_document)
    dump_json(output_dir / "dialogue_occurrences.json", occurrence_document)
    dump_json(output_dir / "localization_manifest.json", manifest)
    write_dialogue_csv(output_dir / "dialogue_units.csv", dialogue_units, occurrence_lookup)
    write_occurrence_csv(output_dir / "dialogue_occurrences.csv", dialogue_occurrences)
    write_manifest_csv(output_dir / "localization_manifest.csv", manifest_units)

    summary_lines = [
        "# Localization catalog summary",
        "",
        "Generated by `tools/build_localization_manifest.py`.",
        "",
        f"- Dialogue occurrences retained: {dialogue_summary['occurrences']:,}",
        f"- Unique dialogue translation units: {dialogue_summary['unique_units']:,}",
        f"- Unresolved LSTR occurrences: {dialogue_summary['unresolved_occurrences']:,}",
        f"- Unified manifest units: {manifest_summary['unit_count']:,}",
        f"- Existing unreviewed translations carried forward: {manifest_summary['translated_unreviewed_count']:,}",
        "",
        "## Categories",
        "",
    ]
    summary_lines.extend(f"- `{key}`: {value:,}" for key, value in sorted(category_counts.items()))
    summary_lines.extend([
        "",
        "## Files",
        "",
        "- `dialogue_units.csv`: primary translator worksheet; one row per exact unique dialogue string.",
        "- `dialogue_occurrences.csv`: every GPL/MAS use site, linked to a dialogue unit by `unit_id`.",
        "- `localization_manifest.csv`: combined dialogue, GFF resource, and EXE-candidate worksheet.",
        "- Matching `.json` files retain nested locations and unresolved LSTR candidate writers.",
        "",
        "Existing non-empty translations in the CSV files are preserved when the generator is run again.",
        "Exact source text is the deduplication key within each namespace. Leading and trailing spaces are preserved.",
        "EXE entries are conservative heuristic candidates, have `status: needs_review`, and are not yet marked translatable.",
        "Duplicate GFF values share one translation unit but retain every container/chunk location.",
    ])
    (output_dir / "README.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(json.dumps(manifest_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
