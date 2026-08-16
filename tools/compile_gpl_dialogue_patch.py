#!/usr/bin/env python3
"""Compile selected dialogue catalog units into a verified GPLDATA.GFF patch."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import shutil
import subprocess
import tempfile
from collections import defaultdict
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
DEFAULT_UNITS = ROOT / "localization/catalog/dialogue_units.csv"
DEFAULT_OCCURRENCES = ROOT / "localization/catalog/dialogue_occurrences.json"
DEFAULT_OPEN_DS = ROOT / "vendor/opends/target/release"
DEFAULT_GPL_DISASM = DEFAULT_OPEN_DS / "gpl-disasm.exe"
DEFAULT_GPL_ASM = DEFAULT_OPEN_DS / "gpl-asm.exe"
DEFAULT_GFF_CAT = DEFAULT_OPEN_DS / "gff-cat.exe"


def run(*arguments: Path | str) -> None:
    subprocess.run([str(item) for item in arguments], check=True)


def escape_gpl_listing_string(value: str) -> str:
    """Use the lossless escaping accepted by gpl-asm's text parser."""
    output: list[str] = []
    for character in value:
        codepoint = ord(character)
        if character == "\\":
            output.append("\\\\")
        elif character == '"':
            output.append('\\"')
        elif character == "\r":
            output.append("\\r")
        elif character == "\n":
            output.append("\\n")
        elif character == "\t":
            output.append("\\t")
        elif character == " " or 0x21 <= codepoint <= 0x7E:
            output.append(character)
        elif codepoint <= 0xFF:
            output.append(f"\\x{codepoint:02x}")
        else:
            raise ValueError(f"GPL listing strings must be byte-valued, found U+{codepoint:04X}")
    return "".join(output)


def replace_listing_strings(
    listing: str, edits: list[dict[str, object]]
) -> tuple[str, list[dict[str, object]]]:
    """Replace exact immediate strings on exact original instruction offsets."""
    lines = listing.splitlines(keepends=True)
    applied: list[dict[str, object]] = []
    for edit in sorted(edits, key=lambda item: int(item["offset"])):
        offset = int(edit["offset"])
        original = str(edit["original"])
        encoded = bytes(edit["encoded"])
        encoded_ascii = encoded.decode("ascii")
        candidates = [
            index for index, line in enumerate(lines)
            if line.lower().startswith(f"{offset:04x}  ")
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"{edit['unit_id']}: expected one instruction at 0x{offset:04X}, "
                f"found {len(candidates)}"
            )
        index = candidates[0]
        needle = f'"{escape_gpl_listing_string(original)}"'
        replacement = f'"{escape_gpl_listing_string(encoded_ascii)}"'
        if lines[index].count(needle) != 1:
            raise ValueError(
                f"{edit['unit_id']}: source fingerprint mismatch at 0x{offset:04X}"
            )
        lines[index] = lines[index].replace(needle, replacement, 1)
        applied.append(
            {
                "unit_id": edit["unit_id"],
                "occurrence_id": edit["occurrence_id"],
                "original_offset": offset,
                "original": original,
                "translation_zh_tw": edit["translation_zh_tw"],
                "encoded_ascii": encoded_ascii,
                "encoded_bytes": len(encoded),
                "source_bytes": len(original.encode("ascii")),
            }
        )
    return "".join(lines), applied


BRANCH_PARAMETER = {
    0x12: 0,  # jump
    0x13: 0,  # local sub
    0x27: 1,  # ifcompare
    0x29: 0,  # orelse
    0x3E: 0,  # if
    0x3F: 0,  # else
    0x63: 0,  # while
    0x64: 0,  # wend
}
# 0x14 (gpl global sub) takes (offset, chunk_id) and is usually a genuine
# cross-chunk call, unaffected by this chunk's own relocation -- EXCEPT when
# chunk_id equals the chunk currently being patched, which does happen (a
# subroutine calling back into its own chunk via the "global" mechanism
# instead of 0x13 "local sub"). relocate_json_strings handles that
# self-reference case directly instead of going through BRANCH_PARAMETER,
# since its target/chunk parameter order is reversed from every other single-
# target opcode. See GLOBAL_SUB_OPCODE below.
#
# The "template" trigger opcodes (0x65 attacktrigger, 0x66 looktrigger, 0x68
# move tiletrigger, 0x69 door tiletrigger, 0x6A move boxtrigger, 0x6B door
# boxtrigger, 0x6C pickup itemtrigger, 0x6D usetrigger, 0x6E talktotrigger,
# 0x6F noorderstrigger, 0x70 usewithtrigger) were investigated for re_42 and
# deliberately NOT added here. Their leading immediate14 fields looked like
# same-chunk offsets at first (e.g. two different 0x6F instances in two
# different GPL-2..5 chunks both used the literal value 100), but that value
# recurs identically across unrelated chunks of very different lengths --
# it is a fixed threshold/radius constant, not a branch target. Their real
# jump target, if any, is more likely carried by the trailing
# `immediate_name`/`complex_access`/`variable(gname)` expression (a symbolic
# reference, similar in spirit to 0x14's cross-chunk call), which does not
# need same-chunk offset relocation. Do not add a numeric param index for
# these opcodes without first confirming which field is genuinely a
# same-chunk offset (e.g. by checking whether the value repeats identically
# across chunks of different lengths, as it does here) -- a wrong guess
# raises a clear "targets non-instruction" error during relocation rather
# than a silent one, so this is safe to leave unhandled for now.

# gpl_menu (0x48): one leading expression (the menu's TEXT-table name),
# then a run of 3-expression entries (choice string, jump target, flag)
# until the terminator byte 0x4A. The jump target sits in the middle of
# each triple and is not covered by BRANCH_PARAMETER.
MENU_OPCODE = 0x48
MENU_ENTRY_WIDTH = 3
MENU_ENTRY_TARGET_INDEX = 1

# gpl_global_sub (0x14): params are (offset, chunk_id), reversed from the
# (chunk_id, offset) order the disassembler's own comments describe them in
# prose -- confirmed empirically (re_42) against real GPL-2/4 call sites.
GLOBAL_SUB_OPCODE = 0x14
GLOBAL_SUB_OFFSET_INDEX = 0
GLOBAL_SUB_CHUNK_INDEX = 1


def relocate_single_target(
    expressions: list[dict[str, object]], offset_map: dict[int, int], where: str
) -> None:
    """Rewrite the one immediate14 branch target among `expressions` in place."""
    targets = [expression for expression in expressions if expression.get("kind") == "immediate14"]
    if len(targets) != 1:
        raise ValueError(f"{where} has a non-literal target")
    old_target = int(targets[0]["value"])
    if old_target not in offset_map:
        raise ValueError(f"{where} targets non-instruction 0x{old_target:04X}")
    targets[0]["value"] = offset_map[old_target]


def packed_string_bytes(value: str) -> int:
    """Return the SSI 7-bit stream size including its 0x03 terminator."""
    try:
        payload = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("GPL compressed strings must be transport-safe ASCII") from exc
    return ((len(payload) + 1) * 7 + 7) // 8


def relocate_json_strings(
    source_document: dict[str, object], edits: list[dict[str, object]], chunk_id: int | None = None
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Replace strings and relocate every instruction and local branch target."""
    document = copy.deepcopy(source_document)
    instructions = document.get("instructions")
    if not isinstance(instructions, list) or not document.get("aligned"):
        raise ValueError("GPL disassembly is missing an aligned instruction list")
    by_offset = {int(edit["offset"]): edit for edit in edits}
    if len(by_offset) != len(edits):
        raise ValueError("multiple dialogue edits target the same instruction offset")
    old_offsets = [int(instruction["offset"]) for instruction in instructions]
    if len(set(old_offsets)) != len(old_offsets):
        raise ValueError("GPL disassembly contains duplicate instruction offsets")
    applied: list[dict[str, object]] = []

    for instruction in instructions:
        old_offset = int(instruction["offset"])
        edit = by_offset.get(old_offset)
        if edit is None:
            continue
        if int(instruction["opcode"]) != 0x4F:
            raise ValueError(f"{edit['unit_id']}: 0x{old_offset:04X} is not gpl print string")
        strings = [
            expression
            for parameter in instruction.get("params", [])
            for expression in parameter
            if expression.get("kind") == "immediate_string"
        ]
        if len(strings) != 1 or strings[0].get("sub_type") != "compressed":
            raise ValueError(f"{edit['unit_id']}: expected one compressed inline string")
        original = str(edit["original"])
        if strings[0].get("value") != original:
            raise ValueError(
                f"{edit['unit_id']}: source fingerprint mismatch at 0x{old_offset:04X}"
            )
        encoded = bytes(edit["encoded"])
        encoded_ascii = encoded.decode("ascii")
        delta = packed_string_bytes(encoded_ascii) - packed_string_bytes(original)
        instruction["length"] = int(instruction["length"]) + delta
        if instruction["length"] <= 0:
            raise ValueError(f"{edit['unit_id']}: replacement produced invalid instruction length")
        strings[0]["value"] = encoded_ascii
        applied.append(
            {
                "unit_id": edit["unit_id"],
                "occurrence_id": edit["occurrence_id"],
                "original_offset": old_offset,
                "original": original,
                "translation_zh_tw": edit["translation_zh_tw"],
                "encoded_ascii": encoded_ascii,
                "encoded_bytes": len(encoded),
                "source_bytes": len(original.encode("ascii")),
                "packed_length_delta": delta,
            }
        )
    missing = sorted(set(by_offset) - {item["original_offset"] for item in applied})
    if missing:
        raise ValueError(f"dialogue edit offsets are not instructions: {missing}")

    offset_map: dict[int, int] = {}
    old_cursor = 0
    new_cursor = 0
    for instruction, old_offset in zip(instructions, old_offsets, strict=True):
        if old_offset != old_cursor:
            raise ValueError(
                f"GPL instruction stream has a gap at 0x{old_cursor:04X}/0x{old_offset:04X}"
            )
        offset_map[old_offset] = new_cursor
        old_cursor += int(source_document["instructions"][len(offset_map) - 1]["length"])
        instruction["offset"] = new_cursor
        new_cursor += int(instruction["length"])
    if old_cursor != int(source_document["total_bytes"]):
        raise ValueError("GPL source instruction lengths do not cover the full chunk")

    for instruction in instructions:
        opcode = int(instruction["opcode"])
        params = instruction.get("params", [])
        parameter_index = BRANCH_PARAMETER.get(opcode)
        if parameter_index is not None:
            if parameter_index >= len(params):
                raise ValueError(f"branch at 0x{instruction['offset']:04X} has no target parameter")
            relocate_single_target(
                params[parameter_index], offset_map, f"branch at 0x{instruction['offset']:04X}"
            )
            continue
        if opcode == MENU_OPCODE:
            entry_params = len(params) - 1
            if entry_params < 0 or entry_params % MENU_ENTRY_WIDTH != 0:
                raise ValueError(
                    f"menu at 0x{instruction['offset']:04X} has an unexpected parameter shape "
                    f"({len(params)} params)"
                )
            for entry in range(entry_params // MENU_ENTRY_WIDTH):
                target_index = 1 + entry * MENU_ENTRY_WIDTH + MENU_ENTRY_TARGET_INDEX
                relocate_single_target(
                    params[target_index],
                    offset_map,
                    f"menu at 0x{instruction['offset']:04X} entry {entry}",
                )
            continue
        if opcode == GLOBAL_SUB_OPCODE and chunk_id is not None:
            # gpl_global_sub (0x14) targets (offset, chunk_id). Cross-chunk
            # calls are unaffected by this chunk's own relocation, but a call
            # can legally target its OWN chunk (re_42 found two such
            # self-references in GPL-2) -- that offset must move with
            # everything else or the call lands on stale, misaligned bytes.
            if len(params) < GLOBAL_SUB_CHUNK_INDEX + 1:
                raise ValueError(f"global sub at 0x{instruction['offset']:04X} has no chunk parameter")
            chunk_targets = [
                expression for expression in params[GLOBAL_SUB_CHUNK_INDEX]
                if expression.get("kind") == "immediate14"
            ]
            if len(chunk_targets) != 1:
                raise ValueError(f"global sub at 0x{instruction['offset']:04X} has a non-literal chunk id")
            if int(chunk_targets[0]["value"]) == chunk_id:
                relocate_single_target(
                    params[GLOBAL_SUB_OFFSET_INDEX],
                    offset_map,
                    f"self-referencing global sub at 0x{instruction['offset']:04X}",
                )

    document["bytes_consumed"] = new_cursor
    document["total_bytes"] = new_cursor
    document["cfg"] = None
    document["cross_chunk_calls"] = []
    return document, applied


def load_selected_edits(
    units_path: Path,
    occurrences_path: Path,
    mapping: dict[str, object],
    unit_ids: list[str],
) -> dict[tuple[str, int], list[dict[str, object]]]:
    with units_path.open("r", encoding="utf-8-sig", newline="") as stream:
        units = {row["unit_id"]: row for row in csv.DictReader(stream)}
    occurrence_document = json.loads(occurrences_path.read_text(encoding="utf-8"))
    occurrences = occurrence_document.get("occurrences")
    if not isinstance(occurrences, list):
        raise ValueError("dialogue occurrence document has no occurrences list")
    requested = set(unit_ids)
    if len(requested) != len(unit_ids):
        raise ValueError("duplicate --unit-id argument")
    missing = sorted(requested - units.keys())
    if missing:
        raise ValueError(f"unknown dialogue unit(s): {missing}")
    for unit_id in requested:
        if not units[unit_id].get("translation_zh_tw"):
            raise ValueError(f"{unit_id}: selected unit has no translation")

    grouped: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    seen: set[str] = set()
    for occurrence in occurrences:
        unit_id = occurrence.get("unit_id")
        if unit_id not in requested:
            continue
        if occurrence.get("unresolved"):
            raise ValueError(f"{occurrence.get('occurrence_id')}: unresolved occurrence")
        kind = str(occurrence.get("kind", "")).strip().upper()
        if kind not in {"GPL", "MAS"}:
            raise ValueError(f"{occurrence.get('occurrence_id')}: unsupported kind {kind!r}")
        if occurrence.get("source") != "inline" or occurrence.get("sub_type") != "compressed":
            raise ValueError(
                f"{occurrence.get('occurrence_id')}: only inline compressed strings are supported"
            )
        unit = units[unit_id]
        grouped[(kind, int(occurrence["chunk_id"]))].append(
            {
                "unit_id": unit_id,
                "occurrence_id": occurrence["occurrence_id"],
                "offset": int(occurrence["offset"]),
                "original": unit["original"],
                "translation_zh_tw": unit["translation_zh_tw"],
                "encoded": encode_text(unit["translation_zh_tw"], mapping),
            }
        )
        seen.add(unit_id)
    absent = sorted(requested - seen)
    if absent:
        raise ValueError(f"selected unit(s) have no supported occurrence: {absent}")
    return grouped


def string_values(disassembly: dict[str, object]) -> list[str]:
    values: list[str] = []
    for instruction in disassembly.get("instructions", []):
        for parameter in instruction.get("params", []):
            for expression in parameter:
                if expression.get("kind") == "immediate_string":
                    values.append(expression.get("value", ""))
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_GPLDATA)
    parser.add_argument("--units", type=Path, default=DEFAULT_UNITS)
    parser.add_argument("--occurrences", type=Path, default=DEFAULT_OCCURRENCES)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--gpl-disasm", type=Path, default=DEFAULT_GPL_DISASM)
    parser.add_argument("--gpl-asm", type=Path, default=DEFAULT_GPL_ASM)
    parser.add_argument("--gff-cat", type=Path, default=DEFAULT_GFF_CAT)
    parser.add_argument("--unit-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    mapping = load_mapping(args.mapping)
    grouped = load_selected_edits(
        args.units, args.occurrences, mapping, args.unit_id
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="darksun-gpl-dialogue-", dir=output.parent) as temporary:
        temporary_root = Path(temporary)
        staging = temporary_root / "package"
        chunks = staging / "chunks"
        listings = staging / "ir"
        chunks.mkdir(parents=True)
        listings.mkdir(parents=True)
        target_records: list[dict[str, object]] = []
        edit_records: list[dict[str, object]] = []

        for (kind, chunk_id), edits in sorted(grouped.items()):
            stem = f"{kind}-{chunk_id}"
            original_chunk = chunks / f"{stem}.original.bin"
            roundtrip_chunk = chunks / f"{stem}.roundtrip.bin"
            patched_chunk = chunks / f"{stem}.bin"
            original_listing = listings / f"{stem}.original.json"
            patched_listing = listings / f"{stem}.patched.json"
            run(args.gff_cat, "extract", source, kind, str(chunk_id), "-o", original_chunk)
            run(
                args.gpl_disasm,
                source,
                "--kind",
                kind,
                "--id",
                str(chunk_id),
                "--json",
                "--no-syms",
                "-o",
                original_listing,
            )
            run(args.gpl_asm, original_listing, "-o", roundtrip_chunk)
            if roundtrip_chunk.read_bytes() != original_chunk.read_bytes():
                raise ValueError(f"{stem}: source chunk failed byte-identical GPL round-trip")
            source_document = json.loads(original_listing.read_text(encoding="utf-8"))
            patched_document, applied = relocate_json_strings(
                source_document, edits, chunk_id
            )
            write_json(patched_listing, patched_document)
            run(args.gpl_asm, patched_listing, "-o", patched_chunk)
            target_records.append(
                {
                    "kind": kind,
                    "chunk_id": chunk_id,
                    "source_bytes": len(original_chunk.read_bytes()),
                    "source_sha256": sha256(original_chunk.read_bytes()),
                    "encoded_byte_length": len(patched_chunk.read_bytes()),
                    "sha256": sha256(patched_chunk.read_bytes()),
                    "file": f"chunks/{stem}.bin",
                }
            )
            for item in applied:
                item.update({"kind": kind, "chunk_id": chunk_id})
                edit_records.append(item)

        current = source
        for index, record in enumerate(target_records):
            next_gff = temporary_root / f"GPLDATA.step-{index}.GFF"
            run(
                args.gff_cat,
                "replace",
                current,
                record["kind"],
                str(record["chunk_id"]),
                chunks / f"{record['kind']}-{record['chunk_id']}.bin",
                "-o",
                next_gff,
            )
            current = next_gff
        patched_gff = staging / "GPLDATA.GFF"
        shutil.copyfile(current, patched_gff)

        original_all = temporary_root / "original-all"
        patched_all = temporary_root / "patched-all"
        run(args.gff_cat, "extract", source, "--all", "-o", original_all)
        run(args.gff_cat, "extract", patched_gff, "--all", "-o", patched_all)
        verification = verify_extracted_gff_chunks(
            original_all, patched_all, target_records, {"GFFI-8.bin"}
        )

        for record in target_records:
            kind, chunk_id = record["kind"], record["chunk_id"]
            json_path = listings / f"{kind}-{chunk_id}.verified.json"
            run(
                args.gpl_disasm,
                patched_gff,
                "--kind",
                kind,
                "--id",
                str(chunk_id),
                "--json",
                "--no-syms",
                "-o",
                json_path,
            )
            document = json.loads(json_path.read_text(encoding="utf-8"))
            if not document.get("aligned") or document.get("bytes_consumed") != document.get("total_bytes"):
                raise ValueError(f"{kind}-{chunk_id}: patched chunk is not instruction-aligned")
            values = string_values(document)
            for edit in [
                item for item in edit_records
                if item["kind"] == kind and item["chunk_id"] == chunk_id
            ]:
                if edit["encoded_ascii"] not in values:
                    raise ValueError(
                        f"{edit['unit_id']}: encoded string did not survive patched disassembly"
                    )

        package = {
            "format": "darksun-gpl-dialogue-patch",
            "version": 1,
            "source": str(source),
            "source_sha256": sha256(source.read_bytes()),
            "patched_file": "GPLDATA.GFF",
            "patched_bytes": len(patched_gff.read_bytes()),
            "patched_sha256": sha256(patched_gff.read_bytes()),
            "units": sorted(set(args.unit_id)),
            "mapping_sha256": sha256(args.mapping.read_bytes()),
            "chunks": target_records,
            "edits": edit_records,
            "verification": verification,
        }
        write_json(staging / "gpl-dialogue-patch.json", package)
        shutil.move(str(staging), str(output))

    print(f"patched_gpldata={output / 'GPLDATA.GFF'}")
    print(f"patched_sha256={package['patched_sha256']}")
    print(f"patched_chunks={len(target_records)}")
    print(f"patched_occurrences={len(edit_records)}")
    print(f"unchanged_chunks={verification['unchanged_non_target_chunks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
