#!/usr/bin/env python3
"""Build v69: class name shows its level inline, e.g. "角鬥士(3)".

Per the user's requested format ("牧師(3) / 聖堂武士(2) / 吟遊詩人(2)"),
this replaces the plain class-name text with a dynamically built
"ClassName(Level)" string per slot -- the level number varies per
character, so it can't be a static table entry like the class name
itself; `class_slotN_label_entry` now reads both `record+0x21..0x23`
(class) and `record+0x24..0x26` (level, per `re_85`) and builds the
mixed CJK-tag/plain-ASCII source live into a FONT-local scratch buffer
before handing it to the existing decode_start pipeline. Plain ASCII
bytes (digits, parentheses) pass through decode_next untouched, so no
new tag range or glyph is needed for the punctuation/digits themselves.

Per the user's explicit choice, the separate "just the level number"
line (`5FB0:1A01`, a small always-resident wrapper that reads no
translatable text of its own, just forwards to a further call) is fully
suppressed now rather than left showing the level twice: since nothing
downstream of that draw depends on it running, the whole 26-byte
wrapper is replaced with a single `retf` (padded with NOPs), matching
the exact byte-for-byte the caller's own stack cleanup after the call
already expects regardless of what the callee does internally.

FONT-side change only touches class_slot1/2/3_label_entry (now dynamic)
plus the new shared `build_class_combined` helper and its scratch
buffer; the class name table/strings and every other identity field are
byte-for-byte unchanged from v68c.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

try:
    from .build_backpack_ui_candidate import ROOT, sha256
    from .build_name_slot_candidate_from_v33 import run
    from .build_view_character_candidate import verify_overlay_relocations
    from .build_view_alignment_reposition_candidate import LABELS
    from .cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache
except ImportError:
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from build_view_character_candidate import verify_overlay_relocations
    from build_view_alignment_reposition_candidate import LABELS
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v69_view_class_level_combined"
V68C_ROOT = ROOT / "scratch_test/cjk_display_staging_v68c_view_class_names_full"
PARENT_EXE_HASH = "3eaabd6208c6d337bf21518bb61a4e29f3421495173b57afd8a9e3e7c6957542"
PARENT_RESOURCE_HASH = "8406e80875998466b53bac6d97a65da5823473ba1f4372141c6fbf2b6e5056e2"
PARENT_FONT_HASH = "1583ae003f82062f13843f63c26eaf0714bccdfd4ebb5294467886afff9c4b24"

LEVEL_LINE_SITE = 0x64C51
LEVEL_LINE_LEN = 26
LEVEL_LINE_ORIGINAL = bytes.fromhex(
    "558becff7610ff760e66ff760a66ff76060ee8b1f783c40c5dcb")


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v68c")
    if image[LEVEL_LINE_SITE:LEVEL_LINE_SITE + LEVEL_LINE_LEN] != LEVEL_LINE_ORIGINAL:
        raise ValueError("level-line wrapper differs")
    verify_overlay_relocations(image, [(LEVEL_LINE_SITE, LEVEL_LINE_SITE + LEVEL_LINE_LEN)])
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    result[LEVEL_LINE_SITE:LEVEL_LINE_SITE + LEVEL_LINE_LEN] = b"\xCB" + b"\x90" * (LEVEL_LINE_LEN - 1)
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("level-line patch changed main MZ relocations")
    allowed = set(range(LEVEL_LINE_SITE, LEVEL_LINE_SITE + LEVEL_LINE_LEN))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v68c")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v68c")
    patched = patch_executable(exe)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-class-level-combined-v69-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"

        mapping = load_mapping(source / "cjk-mapping-v57.json")
        by_char = {e["character"]: e["id"] for e in mapping["entries"]}
        ability_ids = tuple(by_char[c] for c in "".join(LABELS))
        label_ids = (by_char["防"], by_char["禦"], by_char["靈"], by_char["能"],
                     by_char["生"], by_char["命"], by_char["靈"], by_char["能"])
        base_options = dict(backpack_ids=(1303, 100), ability_ids=ability_ids,
            view_character=True, view_y_origin=63, identity=True,
            alignment_position=(44, 149), class_names=True)

        font_path = work / "font.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        original_font = font_path.read_bytes()
        if sha256(original_font) != PARENT_FONT_HASH:
            raise ValueError("v68c FONT does not match the reviewed pre-combine font")
        font = original_font[:FONT_CORE_PAYLOAD_OFFSET] + assemble_name_slot_cache(
            **base_options, label_ids=label_ids)
        font_path.write_bytes(font)
        (target / "DSUN.EXE").write_bytes(patched)
        run(DEFAULT_GFF_CAT, "replace", game / "RESOURCE.GFF", "FONT", "100", font_path, "-o", target / "RESOURCE.GFF")
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "--all", "-o", work / "before")
        run(DEFAULT_GFF_CAT, "extract", target / "RESOURCE.GFF", "--all", "-o", work / "after")
        verification = verify_extracted_gff_chunks(work / "before", work / "after", [
            {"kind": "FONT", "chunk_id": 100, "sha256": sha256(font), "encoded_byte_length": len(font)}])
        preserved = 0
        for path in source.rglob("*"):
            rel = path.relative_to(source)
            if path.is_file() and rel.as_posix() not in {"GAME/DARKSUN/DSUN.EXE", "GAME/DARKSUN/RESOURCE.GFF"}:
                if path.read_bytes() != (build / rel).read_bytes():
                    raise ValueError(f"unexpected copied file difference: {rel}")
                preserved += 1
        manifest = {"format": "darksun-view-class-level-combined", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v68c"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[LEVEL_LINE_SITE, LEVEL_LINE_SITE + LEVEL_LINE_LEN]],
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"class_level_combined": "class name now reads \"ClassName(Level)\" per slot, "
                    "e.g. \"角鬥士(3)\" or \"戰士(2)/德魯伊(3)/靈能師(8)\"",
                "old_level_line": "suppressed (5FB0:1A01 replaced with a no-op retf)",
                "exp_dam_labels": "not in this candidate, still pending (see re_88)"},
            "preserved_parent_files": preserved}
        (build / "build-view-class-level-combined-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V69-READ-ME.txt").write_text(
            "v69: class name now shows its level inline, e.g. GERAKIS's \"角鬥士\"\n"
            "-> \"角鬥士(3)\", K'RATCHEK's three classes each getting their own\n"
            "\"(Level)\" suffix. The old separate level-only line is suppressed\n"
            "(the small always-resident wrapper that used to draw it is now a\n"
            "no-op). EXP:/DAM: labels are not in this candidate -- see re_88.\n"
            "Runtime validation NOT performed by this script.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V68C_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
