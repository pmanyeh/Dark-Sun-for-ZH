#!/usr/bin/env python3
"""Build v72: bottom-panel row spacing adjustment + two glossary terminology fixes.

Extends v71 (multiclass class names fixed, 10-slot glyph pool) with two
independent, unrelated changes the user asked for after reviewing v71 live:

1. Row spacing: the class-name row and the level+EXP row sat only 7px apart
   (Y=106, Y=113), visibly cramped compared to the other two rows' 14px gaps,
   while the bottom (AC+DAM) row had more headroom below it than needed. Per
   the user's own annotated screenshot, the fix is: nudge the level/EXP row
   down (widening the gap under the class-name row), and pull the HP+PSI and
   AC+DAM rows up to close the excess space, without leaving anything
   cramped. New Y positions (previous -> new):
     class name   106 -> 106   (unchanged -- see below)
     level/EXP    113 -> 119   (gap from class name: 7 -> 13)
     HP+PSI       127 -> 128   (gap from level/EXP: 14 -> 9)
     AC+DAM       141 -> 137   (gap from HP+PSI: 14 -> 9)
   The class-name row's own position site (file offset 0x8A1E4) turned out
   to overlap a Borland overlay relocation target the first attempt here
   found the hard way (`verify_overlay_relocations` rejected it) -- moving
   that specific word would corrupt the overlay loader's own segment-fixup
   for that instruction, so it stays at its original Y=106 rather than
   also shifting down a few pixels; the other three rows' repositioning
   already delivers the requested "more breathing room after the class
   row, less wasted space at the bottom" layout.
   All six remaining X/Y position sites live in overlay 48 (same one v70
   already patches for EXP/PSI), still simple in-place 6-byte
   `push dword Y:X` immediate swaps -- no tag redirect needed since only
   the position, not the drawn content, changes. The HP:/PSI: labels' own
   Y (baked into FONT-local `.long` constants by re_89's tag redirect, not
   an EXE immediate) move the same way, directly in
   `cjk_name_slot_cache.asm`.

2. Terminology: reviewed against the user's own glossary
   (`一些名詞對照.md`) and found two mismatches from earlier sessions'
   choices -- Preserver was 保育師, glossary wants 保護者; Thri-kreen (race)
   was 螳螂人, glossary wants 螳螂戰士. Both fixed directly in
   `cjk_name_slot_cache.asm`'s `class_preserver`/`race_7` tables, reusing
   already-mapped glyph ids (保51/護709/者617 for Preserver; the existing
   螳1319/螂1318 plus already-mapped 戰289/士1004 for Thri-kreen -- borrowing
   Fighter's own glyph ids since it's the same two characters). Thief's
   glossary translation (小偷) needs a character (偷) that has no glyph in
   cjk-mapping-v57.json at all -- adding a new glyph is a separate,
   bigger undertaking (font generation pipeline, not just a table edit) and
   is deliberately NOT done here; CILLA's third class stays 盜賊 pending
   that decision.
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

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v72_view_layout_adjust"
V71_ROOT = ROOT / "scratch_test/cjk_display_staging_v71_view_class_multi"
PARENT_EXE_HASH = "178602acc67424899f26fb40bbce761694e118deb5e17531703496b2ec8630e5"
PARENT_RESOURCE_HASH = "233c25d08506643f6ff1f6f14d276f39c9589b634d2a579fd912258a060c1f4f"
PARENT_FONT_HASH = "0303d83b9588843dbb85e9e6ed50feb905db3172eb1e837055d82976cfe4ae4d"

# Six of the seven sites confirmed (re_93) inside overlay 48
# (file_start=0x89E70). Each is a 6-byte `66 68 <X_lo> <X_hi> <Y_lo> <Y_hi>`
# push dword immediate. The class-name row's own site (0x8A1E4, Y=106) is
# deliberately NOT in this list -- see the module docstring: it overlaps a
# Borland overlay relocation target, so it stays at its original position.
LEVEL_SITE = 0x8A214
LEVEL_ORIGINAL = bytes.fromhex("666895007100")  # x=149, y=113
LEVEL_NEW = bytes.fromhex("666895007700")        # x=149, y=119

EXP_SITE = 0x8A281
EXP_ORIGINAL = bytes.fromhex("6668C7007100")  # x=199, y=113
EXP_NEW = bytes.fromhex("6668C7007700")        # x=199, y=119

HP_NUMBER_SITE = 0x8A2CF
HP_NUMBER_ORIGINAL = bytes.fromhex("6668BD007F00")  # x=189, y=127
HP_NUMBER_NEW = bytes.fromhex("6668BD008000")        # x=189, y=128

PSI_NUMBER_SITE = 0x8A345
PSI_NUMBER_ORIGINAL = bytes.fromhex("66680E017F00")  # x=270, y=127
PSI_NUMBER_NEW = bytes.fromhex("66680E018000")        # x=270, y=128

DEF_SITE = 0x8A38C
DEF_ORIGINAL = bytes.fromhex("666895008D00")  # x=149, y=141
DEF_NEW = bytes.fromhex("666895008900")        # x=149, y=137

DAM_SITE = 0x8A3C1
DAM_ORIGINAL = bytes.fromhex("6668C7008D00")  # x=199, y=141
DAM_NEW = bytes.fromhex("6668C7008900")        # x=199, y=137

SITES = [
    ("level_position", LEVEL_SITE, LEVEL_ORIGINAL, LEVEL_NEW),
    ("exp_position", EXP_SITE, EXP_ORIGINAL, EXP_NEW),
    ("hp_number_position", HP_NUMBER_SITE, HP_NUMBER_ORIGINAL, HP_NUMBER_NEW),
    ("psi_number_position", PSI_NUMBER_SITE, PSI_NUMBER_ORIGINAL, PSI_NUMBER_NEW),
    ("def_position", DEF_SITE, DEF_ORIGINAL, DEF_NEW),
    ("dam_position", DAM_SITE, DAM_ORIGINAL, DAM_NEW),
]


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v71")
    ranges = []
    for name, site, original, _ in SITES:
        if image[site:site + len(original)] != original:
            raise ValueError(f"{name} site differs")
        ranges.append((site, site + len(original)))
    verify_overlay_relocations(image, ranges)
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    for name, site, original, new in SITES:
        result[site:site + len(new)] = new
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("layout adjust patch changed main MZ relocations")
    allowed: set[int] = set()
    for _, site, original, _ in SITES:
        allowed |= set(range(site, site + len(original)))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v71")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v71")
    patched = patch_executable(exe)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-layout-adjust-v72-", dir=output.parent) as temporary:
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
            raise ValueError("v71 FONT does not match the reviewed pre-adjust font")
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
        manifest = {"format": "darksun-view-layout-adjust", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v71"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[site, site + len(original)] for _, site, original, _ in SITES],
                "overlay_index": 48,
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"rows": "class name Y unchanged at 106 (overlay relocation conflict), "
                    "level/EXP Y 113->119, HP+PSI Y 127->128, AC+DAM Y 141->137 -- "
                    "widens the class/level gap from 7px to 13px",
                "terminology": "Preserver 保育師->保護者, Thri-kreen 螳螂人->螳螂戰士 "
                    "(per user's glossary); Thief stays 盜賊 -- 小偷 needs a new glyph (偷) "
                    "not yet in cjk-mapping-v57.json, deliberately deferred"},
            "preserved_parent_files": preserved}
        (build / "build-view-layout-adjust-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V72-READ-ME.txt").write_text(
            "v72: bottom-panel row spacing adjustment + two glossary terminology\n"
            "fixes (Preserver 保護者, Thri-kreen 螳螂戰士). Class-name/level rows\n"
            "moved down and given more breathing room; AC+DAM row moved up.\n"
            "Thief intentionally still shows 盜賊, not 小偷 -- that needs a new\n"
            "glyph (偷) added to the font, a separate task from this candidate.\n"
            "Built on v71 (multiclass class names + 10-slot pool carried over\n"
            "unchanged). Runtime validation NOT performed by this script.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V71_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
