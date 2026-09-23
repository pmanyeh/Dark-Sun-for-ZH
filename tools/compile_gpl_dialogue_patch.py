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
# Template trigger opcodes carry a target offset and chunk id. re_42 saw a
# recurring literal 100 in unrelated 0x6F instances, so these were initially
# left untouched. re_44 then proved the general structure with GPL-5's
# `talktotrigger 0x092C, 5, <name>`: 0x092C is an instruction boundary in
# original GPL-5 but translation moved the target while the trigger retained
# the stale number. Relocate only when the declared chunk is this chunk AND
# the offset is an instruction boundary; fixed thresholds such as 100 safely
# remain untouched because they are not in offset_map.
#
# Tile and box triggers lead with map coordinates, e.g. MAS-10's
# `move boxtrigger 32, 1, 9, 1, 822, 80, 0` is (x, y, w, h, offset, chunk,
# flag). Treating their first two parameters as the target left every
# walk-in trigger unrelocated (re_98 section 33). No 0x69/0x6B instance
# exists in GPLDATA; they follow their move counterparts.
TEMPLATE_TRIGGER_TARGET = {
    0x1B: (0, 1),  # inlostrigger: offset, chunk, name, range
    0x1C: (0, 1),  # notinlostrigger: offset, chunk, name, range
    0x65: (0, 1),  # attacktrigger: offset, chunk
    0x66: (0, 1),  # looktrigger: offset, chunk
    0x68: (2, 3),  # move tiletrigger: x, y, offset, chunk, flag
    0x69: (2, 3),  # door tiletrigger: x, y, offset, chunk, flag
    0x6A: (4, 5),  # move boxtrigger: x, y, w, h, offset, chunk, flag
    0x6B: (4, 5),  # door boxtrigger: x, y, w, h, offset, chunk, flag
    0x6C: (0, 1),  # pickup itemtrigger: offset, chunk
    0x6D: (0, 1),  # usetrigger: offset, chunk
    0x6E: (0, 1),  # talktotrigger: offset, chunk
    0x6F: (0, 1),  # noorderstrigger: offset, chunk
    0x70: (2, 3),  # usewithtrigger: offset, chunk
}

# gpl_menu (0x48): one leading expression (the menu's TEXT-table name),
# then a run of 3-expression entries (choice string, jump target, flag)
# until the terminator byte 0x4A. The jump target sits in the middle of
# each triple and is not covered by BRANCH_PARAMETER. All of a menu's
# option strings live on the same instruction offset, so the dialogue
# catalog records one occurrence per option but they all share that offset
# -- relocate_json_strings must accept a list of edits per offset instead
# of assuming one.
MENU_OPCODE = 0x48
MENU_ENTRY_WIDTH = 3
MENU_ENTRY_TEXT_INDEX = 0
MENU_ENTRY_TARGET_INDEX = 1

# gpl_global_sub (0x14): params are (offset, chunk_id), reversed from the
# (chunk_id, offset) order the disassembler's own comments describe them in
# prose -- confirmed empirically (re_42) against real GPL-2/4 call sites.
GLOBAL_SUB_OPCODE = 0x14
GLOBAL_SUB_OFFSET_INDEX = 0
GLOBAL_SUB_CHUNK_INDEX = 1


# Every instruction that names another chunk's offset: (offset index, chunk
# index). relocate_json_strings only rewrites these when they point back into
# the chunk being edited; retarget_cross_chunk_references handles the rest.
CROSS_CHUNK_TARGET = {
    GLOBAL_SUB_OPCODE: (GLOBAL_SUB_OFFSET_INDEX, GLOBAL_SUB_CHUNK_INDEX),
    **TEMPLATE_TRIGGER_TARGET,
}


def instruction_offset_map(
    original: dict[str, object], patched: dict[str, object], where: str
) -> dict[int, int]:
    """Map each original instruction offset to its offset in the patched chunk."""
    original_instructions = original["instructions"]
    patched_instructions = patched["instructions"]
    if len(original_instructions) != len(patched_instructions):
        raise ValueError(f"{where}: instruction count differs from the baseline")
    return {
        int(before["offset"]): int(after["offset"])
        for before, after in zip(original_instructions, patched_instructions, strict=True)
    }


def retarget_cross_chunk_references(
    baseline: dict[str, object],
    current: dict[str, object],
    offset_maps: dict[int, dict[int, int]],
    where: str,
) -> list[dict[str, int]]:
    """Point calls and triggers into relocated GPL chunks at their new offsets.

    The target is always derived from the baseline listing, so running this
    again on an already corrected chunk changes nothing.
    """
    baseline_instructions = baseline["instructions"]
    current_instructions = current["instructions"]
    if len(baseline_instructions) != len(current_instructions):
        raise ValueError(f"{where}: instruction count differs from the baseline")
    relocations: list[dict[str, int]] = []
    for before, after in zip(baseline_instructions, current_instructions, strict=True):
        shape = CROSS_CHUNK_TARGET.get(int(before["opcode"]))
        if shape is None:
            continue
        target_index, chunk_index = shape
        params = before.get("params", [])
        if max(target_index, chunk_index) >= len(params):
            continue
        chunk_values = [item for item in params[chunk_index] if item.get("kind") == "immediate14"]
        target_values = [item for item in params[target_index] if item.get("kind") == "immediate14"]
        if len(chunk_values) != 1 or len(target_values) != 1:
            continue
        target_chunk = int(chunk_values[0]["value"])
        offset_map = offset_maps.get(target_chunk)
        if offset_map is None:
            continue
        original_target = int(target_values[0]["value"])
        if original_target not in offset_map:
            raise ValueError(
                f"{where} 0x{int(before['offset']):04X} targets GPL-{target_chunk} "
                f"non-instruction 0x{original_target:04X}"
            )
        current_values = [
            item for item in after["params"][target_index] if item.get("kind") == "immediate14"
        ]
        desired = offset_map[original_target]
        if int(current_values[0]["value"]) != desired:
            current_values[0]["value"] = desired
            relocations.append(
                {
                    "offset": int(after["offset"]),
                    "opcode": int(before["opcode"]),
                    "target_chunk": target_chunk,
                    "original_target": original_target,
                    "relocated_target": desired,
                }
            )
    return relocations


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


def relocate_template_trigger_target(
    params: list[list[dict[str, object]]],
    offset_map: dict[int, int],
    chunk_id: int | None,
    target_index: int,
    chunk_index: int,
    where: str,
) -> None:
    """Relocate a template-trigger target only for a proven same-chunk call."""
    if chunk_id is None or max(target_index, chunk_index) >= len(params):
        return
    chunk_values = [item for item in params[chunk_index] if item.get("kind") == "immediate14"]
    target_values = [item for item in params[target_index] if item.get("kind") == "immediate14"]
    if len(chunk_values) != 1 or len(target_values) != 1:
        return
    if int(chunk_values[0]["value"]) != chunk_id:
        return
    old_target = int(target_values[0]["value"])
    if old_target in offset_map:
        target_values[0]["value"] = offset_map[old_target]


def packed_string_bytes(value: str) -> int:
    """Return the SSI 7-bit stream size including its 0x03 terminator."""
    try:
        payload = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("GPL compressed strings must be transport-safe ASCII") from exc
    return ((len(payload) + 1) * 7 + 7) // 8


def parse_fixed_entry_requirement(value: str) -> tuple[str, int, int, int]:
    """Parse ``KIND:ID:OFFSET:OPCODE`` for an externally addressed GPL entry."""
    parts = value.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "fixed entry must be KIND:ID:OFFSET:OPCODE (for example GPL:3:0x07C0:0x2A)"
        )
    kind = parts[0].upper()
    if kind not in {"GPL", "MAS"}:
        raise argparse.ArgumentTypeError(f"unsupported fixed-entry kind {parts[0]!r}")
    try:
        chunk_id, offset, opcode = (int(item, 0) for item in parts[1:])
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid fixed entry {value!r}") from exc
    if chunk_id < 0 or offset < 0 or not 0 <= opcode <= 0xFF:
        raise argparse.ArgumentTypeError(f"out-of-range fixed entry {value!r}")
    return kind, chunk_id, offset, opcode


def verify_fixed_entry_requirements(
    kind: str, chunk_id: int, payload: bytes, requirements: list[tuple[str, int, int, int]]
) -> None:
    """Refuse a variable-length patch which moves an externally fixed entry."""
    for required_kind, required_id, offset, opcode in requirements:
        if (kind, chunk_id) != (required_kind, required_id):
            continue
        actual = payload[offset] if offset < len(payload) else None
        if actual != opcode:
            actual_text = "past end of chunk" if actual is None else f"0x{actual:02X}"
            raise ValueError(
                f"{kind}-{chunk_id}: fixed external entry 0x{offset:04X} must start "
                f"with 0x{opcode:02X}, found {actual_text}"
            )


def verify_external_entry_boundaries(
    kind: str,
    chunk_id: int,
    document: dict[str, object],
    requirements: list[tuple[str, int, int, int]],
) -> None:
    """Ensure diagnostic fixed entries remain *instruction* boundaries.

    A byte-only check is insufficient: a variable-length rewrite may put an
    unrelated instruction with the same opcode at the former entry address.
    The verified disassembly is the authoritative post-assembly layout, so
    require both the original offset and its opcode to survive there.
    """
    instructions = document.get("instructions")
    if not isinstance(instructions, list):
        raise ValueError(f"{kind}-{chunk_id}: verified disassembly has no instructions")
    boundaries = {
        int(instruction["offset"]): int(instruction["opcode"])
        for instruction in instructions
    }
    for required_kind, required_id, offset, opcode in requirements:
        if (kind, chunk_id) != (required_kind, required_id):
            continue
        actual = boundaries.get(offset)
        if actual != opcode:
            if actual is None:
                actual_text = "not an instruction boundary"
            else:
                actual_text = f"opcode 0x{actual:02X}"
            raise ValueError(
                f"{kind}-{chunk_id}: external entry 0x{offset:04X} must remain an "
                f"instruction boundary with opcode 0x{opcode:02X}, found {actual_text}"
            )


def parse_external_entry_listing(value: str) -> list[int]:
    """Parse the one-hex-offset-per-line output of ``gpl-disasm --entries``.

    The disassembler discovers local-sub function entries structurally; this
    is not by itself proof that an engine-side table stores those offsets.
    """
    entries: list[int] = []
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = int(stripped, 0)
        except ValueError as exc:
            raise ValueError(f"invalid gpl-disasm entry listing line {stripped!r}") from exc
        if entry < 0:
            raise ValueError(f"negative gpl-disasm entry {stripped!r}")
        entries.append(entry)
    if not entries:
        raise ValueError("gpl-disasm returned no external entries")
    return entries


def external_entry_requirements(
    gpl_disasm: Path, source: Path, kind: str, chunk_id: int, original_chunk: bytes
) -> list[tuple[str, int, int, int]]:
    """Capture every discovered local-sub entry as a fixed-layout probe."""
    completed = subprocess.run(
        [
            str(gpl_disasm), str(source), "--kind", kind, "--id", str(chunk_id),
            "--entries", "--no-syms",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    requirements: list[tuple[str, int, int, int]] = []
    for offset in parse_external_entry_listing(completed.stdout):
        if offset >= len(original_chunk):
            raise ValueError(
                f"{kind}-{chunk_id}: external entry 0x{offset:04X} is past source chunk"
            )
        requirements.append((kind, chunk_id, offset, original_chunk[offset]))
    return requirements


def relocate_json_strings(
    source_document: dict[str, object], edits: list[dict[str, object]], chunk_id: int | None = None
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Replace strings and relocate every instruction and local branch target."""
    document = copy.deepcopy(source_document)
    instructions = document.get("instructions")
    if not isinstance(instructions, list) or not document.get("aligned"):
        raise ValueError("GPL disassembly is missing an aligned instruction list")
    by_offset: dict[int, list[dict[str, object]]] = {}
    for edit in edits:
        by_offset.setdefault(int(edit["offset"]), []).append(edit)
    old_offsets = [int(instruction["offset"]) for instruction in instructions]
    if len(set(old_offsets)) != len(old_offsets):
        raise ValueError("GPL disassembly contains duplicate instruction offsets")
    applied: list[dict[str, object]] = []

    def apply_string_edit(
        string_expression: dict[str, object], edit: dict[str, object], old_offset: int
    ) -> int:
        """Fingerprint-check and rewrite one compressed string in place, returning its packed-byte delta."""
        original = str(edit["original"])
        if string_expression.get("value") != original:
            raise ValueError(
                f"{edit['unit_id']}: source fingerprint mismatch at 0x{old_offset:04X}"
            )
        encoded = bytes(edit["encoded"])
        encoded_ascii = encoded.decode("ascii")
        delta = packed_string_bytes(encoded_ascii) - packed_string_bytes(original)
        string_expression["value"] = encoded_ascii
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
        return delta

    for instruction in instructions:
        old_offset = int(instruction["offset"])
        offset_edits = by_offset.get(old_offset)
        if not offset_edits:
            continue
        opcode = int(instruction["opcode"])
        params = instruction.get("params", [])
        if opcode == 0x4F:
            if len(offset_edits) != 1:
                raise ValueError(
                    "multiple dialogue edits target print-string instruction at "
                    f"0x{old_offset:04X}"
                )
            strings = [
                expression
                for parameter in params
                for expression in parameter
                if expression.get("kind") == "immediate_string"
            ]
            if len(strings) != 1 or strings[0].get("sub_type") != "compressed":
                raise ValueError(f"{offset_edits[0]['unit_id']}: expected one compressed inline string")
            delta = apply_string_edit(strings[0], offset_edits[0], old_offset)
            instruction["length"] = int(instruction["length"]) + delta
            if instruction["length"] <= 0:
                raise ValueError(
                    f"{offset_edits[0]['unit_id']}: replacement produced invalid instruction length"
                )
        elif opcode == MENU_OPCODE:
            # Every option in this menu shares this one instruction offset, so
            # offset_edits may hold several entries; match each to its option
            # by exact original text (menu option text is not otherwise
            # ordered/indexed in the dialogue catalog) and reject anything
            # ambiguous or unmatched instead of guessing.
            entry_params = len(params) - 1
            if entry_params < 0 or entry_params % MENU_ENTRY_WIDTH != 0:
                raise ValueError(
                    f"menu at 0x{old_offset:04X} has an unexpected parameter shape "
                    f"({len(params)} params)"
                )
            num_entries = entry_params // MENU_ENTRY_WIDTH
            # An option's text is not always an inline literal: GPL-141's
            # 0x0A98 menu ends with a string variable (GSTR[5]) and GPL-143's
            # 0x0797 menu starts with INTRODUCE (the active character's name).
            # Such options are left untouched. Only inline compressed
            # literals can be matched to an edit, so an edit aimed at any
            # other option still fails below with "no unclaimed menu entry".
            entry_strings: list[dict[str, object] | None] = []
            for entry in range(num_entries):
                text_index = 1 + entry * MENU_ENTRY_WIDTH + MENU_ENTRY_TEXT_INDEX
                expressions = params[text_index]
                if (
                    len(expressions) == 1
                    and expressions[0].get("kind") == "immediate_string"
                    and expressions[0].get("sub_type") == "compressed"
                ):
                    entry_strings.append(expressions[0])
                else:
                    entry_strings.append(None)
            claimed = [False] * num_entries
            total_delta = 0
            for edit in offset_edits:
                original = str(edit["original"])
                candidates = [
                    index for index in range(num_entries)
                    if not claimed[index]
                    and entry_strings[index] is not None
                    and entry_strings[index].get("value") == original
                ]
                if not candidates:
                    raise ValueError(
                        f"{edit['unit_id']}: no unclaimed menu entry text matches source at "
                        f"0x{old_offset:04X}"
                    )
                index = candidates[0]
                claimed[index] = True
                total_delta += apply_string_edit(entry_strings[index], edit, old_offset)
            instruction["length"] = int(instruction["length"]) + total_delta
            if instruction["length"] <= 0:
                raise ValueError(
                    f"menu at 0x{old_offset:04X}: replacement produced invalid instruction length"
                )
        else:
            raise ValueError(
                f"{offset_edits[0]['unit_id']}: 0x{old_offset:04X} is not gpl print string or gpl menu"
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
            continue
        template_shape = TEMPLATE_TRIGGER_TARGET.get(opcode)
        if template_shape is not None:
            target_index, target_chunk_index = template_shape
            relocate_template_trigger_target(
                params,
                offset_map,
                chunk_id,
                target_index,
                target_chunk_index,
                f"template trigger at 0x{instruction['offset']:04X}",
            )

    document["bytes_consumed"] = new_cursor
    document["total_bytes"] = new_cursor
    document["cfg"] = None
    document["cross_chunk_calls"] = []
    return document, applied


def relocate_gpli_event_targets(
    source: bytes, offset_maps: dict[int, dict[int, int]]
) -> tuple[bytes, list[dict[str, int]]]:
    """Relocate GPLI-1's ``(event_id, offset, gpl_chunk)`` records.

    GPLI is a six-byte little-endian table used by the region-event loader.
    Its offsets are code addresses into GPL chunks, so a translated chunk
    must move these entries in lockstep with branches and template triggers.
    Only offsets that are known original instruction boundaries are changed.
    """
    record_size = 6
    if len(source) % record_size:
        raise ValueError(f"GPLI-1 has invalid {len(source)}-byte record layout")
    patched = bytearray(source)
    relocated: list[dict[str, int]] = []
    for record_offset in range(0, len(source), record_size):
        event_id = int.from_bytes(source[record_offset:record_offset + 2], "little")
        old_target = int.from_bytes(source[record_offset + 2:record_offset + 4], "little")
        chunk_id = int.from_bytes(source[record_offset + 4:record_offset + 6], "little")
        offset_map = offset_maps.get(chunk_id)
        if offset_map is None or old_target not in offset_map:
            continue
        new_target = offset_map[old_target]
        if new_target == old_target:
            continue
        patched[record_offset + 2:record_offset + 4] = new_target.to_bytes(2, "little")
        relocated.append(
            {
                "record_offset": record_offset,
                "event_id": event_id,
                "chunk_id": chunk_id,
                "original_offset": old_target,
                "relocated_offset": new_target,
            }
        )
    return bytes(patched), relocated


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
    parser.add_argument(
        "--prior-package",
        type=Path,
        help="an existing darksun-gpl-dialogue-patch package.json to layer this patch on top of",
    )
    parser.add_argument("--units", type=Path, default=DEFAULT_UNITS)
    parser.add_argument("--occurrences", type=Path, default=DEFAULT_OCCURRENCES)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--gpl-disasm", type=Path, default=DEFAULT_GPL_DISASM)
    parser.add_argument("--gpl-asm", type=Path, default=DEFAULT_GPL_ASM)
    parser.add_argument("--gff-cat", type=Path, default=DEFAULT_GFF_CAT)
    parser.add_argument(
        "--require-fixed-entry",
        action="append",
        type=parse_fixed_entry_requirement,
        default=[],
        metavar="KIND:ID:OFFSET:OPCODE",
        help="require an externally addressed entry to retain its byte offset and opcode",
    )
    parser.add_argument(
        "--preserve-external-entries",
        action="store_true",
        help=(
            "diagnostic: preserve every original gpl-disasm --entries "
            "(discovered local-sub) boundary"
        ),
    )
    parser.add_argument("--unit-id", action="append", default=[])
    parser.add_argument(
        "--unit-id-file",
        type=Path,
        help="text file with one dialogue unit id per line",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.unit_id_file:
        args.unit_id.extend(
            line.strip()
            for line in args.unit_id_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    if not args.unit_id:
        raise ValueError("select dialogue units with --unit-id or --unit-id-file")

    prior_package: dict[str, object] | None = None
    if args.prior_package:
        prior_package = json.loads(args.prior_package.read_text(encoding="utf-8"))
        if prior_package.get("format") != "darksun-gpl-dialogue-patch":
            raise ValueError(f"unsupported prior package: {args.prior_package}")
        source = args.prior_package.parent / str(prior_package["patched_file"])
        baseline = Path(str(prior_package["source"]))
        if sha256(baseline.read_bytes()) != prior_package["source_sha256"]:
            raise ValueError("prior package baseline GPLDATA.GFF does not match its own manifest")
        if sha256(source.read_bytes()) != prior_package["patched_sha256"]:
            raise ValueError("prior package patched GPLDATA.GFF does not match its own manifest")
    else:
        source = args.source.resolve()
        baseline = source
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    mapping = load_mapping(args.mapping)
    grouped = load_selected_edits(
        args.units, args.occurrences, mapping, args.unit_id
    )
    if prior_package:
        prior_targets = {
            (str(record["kind"]), int(record["chunk_id"]))
            for record in prior_package["chunks"]
        }
        overlapping_targets = sorted(set(grouped) & prior_targets)
        if overlapping_targets:
            formatted = ", ".join(f"{kind}-{chunk_id}" for kind, chunk_id in overlapping_targets)
            raise ValueError(
                "prior package already modifies selected dialogue chunks; "
                f"recompile their combined unit set from the pristine baseline: {formatted}"
            )
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="darksun-gpl-dialogue-", dir=output.parent) as temporary:
        temporary_root = Path(temporary)
        staging = temporary_root / "package"
        if args.prior_package:
            shutil.copytree(args.prior_package.parent, staging)
        chunks = staging / "chunks"
        listings = staging / "ir"
        chunks.mkdir(parents=True, exist_ok=True)
        listings.mkdir(parents=True, exist_ok=True)
        target_records: list[dict[str, object]] = (
            list(prior_package["chunks"]) if prior_package else []
        )
        edit_records: list[dict[str, object]] = (
            list(prior_package["edits"]) if prior_package else []
        )
        new_target_records: list[dict[str, object]] = []
        new_edit_records: list[dict[str, object]] = []
        gpl_offset_maps: dict[int, dict[int, int]] = {}
        entry_requirements_by_target: dict[
            tuple[str, int], list[tuple[str, int, int, int]]
        ] = {}

        for (kind, chunk_id), edits in sorted(grouped.items()):
            stem = f"{kind}-{chunk_id}"
            print(f"chunk {stem} edits={len(edits)}", flush=True)
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
            entry_requirements = list(args.require_fixed_entry)
            if args.preserve_external_entries:
                entry_requirements.extend(
                    external_entry_requirements(
                        args.gpl_disasm, source, kind, chunk_id, original_chunk.read_bytes()
                    )
                )
            entry_requirements_by_target[(kind, chunk_id)] = entry_requirements
            source_document = json.loads(original_listing.read_text(encoding="utf-8"))
            try:
                patched_document, applied = relocate_json_strings(
                    source_document, edits, chunk_id
                )
            except ValueError as exc:
                print(f"skip {stem}: {exc}", flush=True)
                continue
            if kind == "GPL":
                original_instructions = source_document["instructions"]
                patched_instructions = patched_document["instructions"]
                if len(original_instructions) != len(patched_instructions):
                    raise ValueError(f"{stem}: instruction count changed during relocation")
                gpl_offset_maps[chunk_id] = {
                    int(original["offset"]): int(patched["offset"])
                    for original, patched in zip(original_instructions, patched_instructions, strict=True)
                }
            write_json(patched_listing, patched_document)
            run(args.gpl_asm, patched_listing, "-o", patched_chunk)
            verify_fixed_entry_requirements(
                kind, chunk_id, patched_chunk.read_bytes(), entry_requirements
            )
            new_target_records.append(
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
                new_edit_records.append(item)

        gpli_original = chunks / "GPLI-1.original.bin"
        gpli_patched = chunks / "GPLI-1.bin"
        run(args.gff_cat, "extract", source, "GPLI", "1", "-o", gpli_original)
        relocated_gpli, gpli_relocations = relocate_gpli_event_targets(
            gpli_original.read_bytes(), gpl_offset_maps
        )
        if gpli_relocations:
            gpli_patched.write_bytes(relocated_gpli)
            new_target_records.append(
                {
                    "kind": "GPLI",
                    "chunk_id": 1,
                    "source_bytes": len(gpli_original.read_bytes()),
                    "source_sha256": sha256(gpli_original.read_bytes()),
                    "encoded_byte_length": len(relocated_gpli),
                    "sha256": sha256(relocated_gpli),
                    "file": "chunks/GPLI-1.bin",
                    "relocated_event_targets": gpli_relocations,
                }
            )

        replaced_targets = {(record["kind"], record["chunk_id"]) for record in new_target_records}
        target_records = [
            record for record in target_records
            if (record["kind"], record["chunk_id"]) not in replaced_targets
        ]
        target_records.extend(new_target_records)
        edit_records.extend(new_edit_records)

        current = source
        for index, record in enumerate(new_target_records):
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
        # Calls and triggers in other chunks still hold baseline offsets into
        # every relocated GPL chunk (including prior-package chunks); point
        # them at the new offsets across the whole file.
        baseline_listings = temporary_root / "baseline-listings"
        current_listings = temporary_root / "current-listings"
        run(args.gpl_disasm, baseline, "--all", "--json", "--no-syms", "-o", baseline_listings)
        run(args.gpl_disasm, current, "--all", "--json", "--no-syms", "-o", current_listings)
        relocated_gpl = sorted(
            int(record["chunk_id"]) for record in target_records if record["kind"] == "GPL"
        )
        cross_offset_maps = {
            chunk_id: instruction_offset_map(
                json.loads((baseline_listings / f"GPL-{chunk_id}.json").read_text(encoding="utf-8")),
                json.loads((current_listings / f"GPL-{chunk_id}.json").read_text(encoding="utf-8")),
                f"GPL-{chunk_id}",
            )
            for chunk_id in relocated_gpl
        }
        records_by_target = {(record["kind"], record["chunk_id"]): record for record in target_records}
        cross_relocations_total = 0
        for listing in sorted(current_listings.glob("*.json")):
            kind, _, chunk_text = listing.stem.partition("-")
            chunk_id = int(chunk_text)
            stem = f"{kind}-{chunk_id}"
            current_document = json.loads(listing.read_text(encoding="utf-8"))
            baseline_document = json.loads(
                (baseline_listings / listing.name).read_text(encoding="utf-8")
            )
            relocations = retarget_cross_chunk_references(
                baseline_document, current_document, cross_offset_maps, stem
            )
            if not relocations:
                continue
            cross_relocations_total += len(relocations)
            print(f"retarget {stem}: {len(relocations)} cross-chunk reference(s)", flush=True)
            retargeted_listing = listings / f"{stem}.retargeted.json"
            retargeted_chunk = chunks / f"{stem}.bin"
            write_json(retargeted_listing, current_document)
            run(args.gpl_asm, retargeted_listing, "-o", retargeted_chunk)
            payload = retargeted_chunk.read_bytes()
            if len(payload) != int(current_document["total_bytes"]):
                raise ValueError(f"{stem}: retargeting changed the chunk length")
            verify_fixed_entry_requirements(
                kind, chunk_id, payload, list(args.require_fixed_entry)
            )
            next_gff = temporary_root / f"GPLDATA.retarget-{stem}.GFF"
            run(args.gff_cat, "replace", current, kind, str(chunk_id), retargeted_chunk, "-o", next_gff)
            current = next_gff
            record = records_by_target.get((kind, chunk_id))
            if record is None:
                baseline_chunk = chunks / f"{stem}.baseline.bin"
                run(args.gff_cat, "extract", baseline, kind, str(chunk_id), "-o", baseline_chunk)
                record = {
                    "kind": kind,
                    "chunk_id": chunk_id,
                    "source_bytes": len(baseline_chunk.read_bytes()),
                    "source_sha256": sha256(baseline_chunk.read_bytes()),
                    "file": f"chunks/{stem}.bin",
                }
                target_records.append(record)
                records_by_target[(kind, chunk_id)] = record
                new_target_records.append(record)
                entry_requirements_by_target[(kind, chunk_id)] = list(args.require_fixed_entry)
            record["encoded_byte_length"] = len(payload)
            record["sha256"] = sha256(payload)
            record["relocated_cross_chunk_targets"] = relocations
            if (kind, chunk_id) not in entry_requirements_by_target:
                entry_requirements_by_target[(kind, chunk_id)] = list(args.require_fixed_entry)
            if record not in new_target_records:
                new_target_records.append(record)

        patched_gff = staging / "GPLDATA.GFF"
        shutil.copyfile(current, patched_gff)

        original_all = temporary_root / "original-all"
        patched_all = temporary_root / "patched-all"
        run(args.gff_cat, "extract", baseline, "--all", "-o", original_all)
        run(args.gff_cat, "extract", patched_gff, "--all", "-o", patched_all)
        verification = verify_extracted_gff_chunks(
            original_all, patched_all, target_records, {"GFFI-8.bin"}
        )

        for record in new_target_records:
            kind, chunk_id = record["kind"], record["chunk_id"]
            if kind not in {"GPL", "MAS"}:
                continue
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
            verify_external_entry_boundaries(
                kind,
                chunk_id,
                document,
                entry_requirements_by_target[(kind, chunk_id)],
            )
            values = string_values(document)
            for edit in [
                item for item in new_edit_records
                if item["kind"] == kind and item["chunk_id"] == chunk_id
            ]:
                if edit["encoded_ascii"] not in values:
                    raise ValueError(
                        f"{edit['unit_id']}: encoded string did not survive patched disassembly"
                    )

        prior_unit_ids = {
            str(item["unit_id"])
            for item in (prior_package.get("edits", []) if prior_package else [])
            if item.get("unit_id")
        }
        package = {
            "format": "darksun-gpl-dialogue-patch",
            "version": 1,
            "source": str(baseline),
            "source_sha256": sha256(baseline.read_bytes()),
            "patched_file": "GPLDATA.GFF",
            "patched_bytes": len(patched_gff.read_bytes()),
            "patched_sha256": sha256(patched_gff.read_bytes()),
            "units": sorted(
                set(args.unit_id)
                | set(prior_package.get("units", []) if prior_package else [])
                | prior_unit_ids
            ),
            "mapping_sha256": sha256(args.mapping.read_bytes()),
            "chunks": target_records,
            "edits": edit_records,
            "verification": verification,
        }
        for inherited_key in ("name_records", "abi_constraint"):
            if prior_package and inherited_key in prior_package:
                package[inherited_key] = prior_package[inherited_key]
        write_json(staging / "gpl-dialogue-patch.json", package)
        shutil.move(str(staging), str(output))

    print(f"patched_gpldata={output / 'GPLDATA.GFF'}")
    print(f"patched_sha256={package['patched_sha256']}")
    print(f"patched_chunks={len(target_records)}")
    print(f"patched_occurrences={len(edit_records)}")
    print(f"cross_chunk_retargets={cross_relocations_total}")
    print(f"unchanged_chunks={verification['unchanged_non_target_chunks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
