#!/usr/bin/env python3
"""Build v70: EXP joins Level's row, PSI joins HP's row (4-row bottom layout).

Per the user's own mockup, the VIEW CHARACTER lower panel should read as
four rows instead of six: class name(s) full-width, then level+EXP,
HP+PSI, and AC+DAM each sharing one row as left/right columns. AC/DAM
already share a row natively (x=149/x=199 at y=141) and class/level's own
rows are left untouched, so the only two fields that actually move are:

- EXP: y=120 -> y=113 (level's row), x=149 -> x=199 (matching the AC/DAM
  right-column convention), so it now sits to the right of the level
  number(s).
- PSI (both its "PSI:"->"靈能:" label and its number): y=134 -> y=127
  (HP's row), x=149/189 -> x=230/... -- pushed further right than the
  AC/DAM right column because "生命:99/99" is wider than "防禦:99".

Every position on this screen turned out to be a single `push dword
Y:X`-style immediate (`66 68 <X_lo> <X_hi> <Y_lo> <Y_hi>`) inside VIEW's
own draw sequence, immediately before the call that uses it -- confirmed
by live-tracing all seven fields (class/level/EXP/HP-number/PSI-number/
AC/DAM) back from their `4A41` jump-table call sites. All seven pushes
live inside the same overlay unit 48 (`file_start=0x89E70`, the one
`re_89`'s HP:/PSI: label patch already uses) at file offsets confirmed
via `ovr-map.py`, so unlike the labels themselves these numeric-position
literals need no tag redirect at all -- just an in-place 4-byte swap,
since nothing about *what* gets drawn changes, only *where*.

PSI's label position is a different story: `re_89`'s tag redirect already
replaced that call's own position push with a FONT-local hardcoded
`.long` in `view_psi_decoded` (the original EXE bytes for that argument
no longer exist), so moving it means editing that literal in
`cjk_name_slot_cache.asm` and reassembling FONT -- done directly in the
shared asm source for this candidate, alongside reverting v69's abandoned
class_slotN_label_entry (see re_92) back to v68c's plain table lookup,
which the source still needed undoing before any further FONT rebuild.

This candidate is built on **v68b**, not v68c: while reverting v69's
combined format, live testing turned up a separate, pre-existing bug
(re_93) where the 2-/3-class draw paths' combined-render pattern makes
every class-name pointer in a multiclass character alias whichever slot
decoded last (K'RATCHEK/CERMAK/CILLA all showed one name repeated,
independent of and unrelated to this candidate's own EXP/PSI position
changes). A same-session attempt at a proper fix (per-slot buffers, more
physical glyph slots) introduced worse corruption from a font-pointer
addressing mistake, and even the addressing fix didn't fully resolve it
within the time available -- so rather than ship broken multiclass names,
this candidate deliberately drops back to v68b's parent, which never
patched the 2-/3-class EXE sites in the first place. Multiclass
characters show their class names in English (safe, correct, matches
v68b's already-validated scope); only single-class characters (e.g.
GERAKIS) get 中文. See re_93 for the full investigation and what a real
fix would need.
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

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v70_view_layout_reflow"
V68B_ROOT = ROOT / "scratch_test/cjk_display_staging_v68b_view_class_names_slot1"
PARENT_EXE_HASH = "78a7f1bab8b168f97bafc0b0574b9365ee3d5474010cbdd02c93b9a03b36f4d9"
PARENT_RESOURCE_HASH = "8406e80875998466b53bac6d97a65da5823473ba1f4372141c6fbf2b6e5056e2"
PARENT_FONT_HASH = "1583ae003f82062f13843f63c26eaf0714bccdfd4ebb5294467886afff9c4b24"

# Both sites confirmed via ovr-map.py to sit inside overlay 48
# (file_start=0x89E70, file_end=0x8AD73), the same overlay re_89's HP:/
# PSI: label redirect already patches.
EXP_POSITION_SITE = 0x8A281
EXP_POSITION_ORIGINAL = bytes.fromhex("66689500" "7800")  # x=149, y=120
EXP_POSITION_NEW = bytes.fromhex("6668C700" "7100")        # x=199, y=113

PSI_NUMBER_POSITION_SITE = 0x8A345
PSI_NUMBER_POSITION_ORIGINAL = bytes.fromhex("6668BD00" "8600")  # x=189, y=134
PSI_NUMBER_POSITION_NEW = bytes.fromhex("66680E01" "7F00")        # x=270, y=127

SITES = [
    ("exp_position", EXP_POSITION_SITE, EXP_POSITION_ORIGINAL, EXP_POSITION_NEW),
    ("psi_number_position", PSI_NUMBER_POSITION_SITE, PSI_NUMBER_POSITION_ORIGINAL, PSI_NUMBER_POSITION_NEW),
]


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v68b")
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
        raise ValueError("layout reflow patch changed main MZ relocations")
    allowed: set[int] = set()
    for name, site, original, _ in SITES:
        allowed |= set(range(site, site + len(original)))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v68b")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v68b")
    patched = patch_executable(exe)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-layout-reflow-v70-", dir=output.parent) as temporary:
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
            raise ValueError("v68b FONT does not match the reviewed pre-reflow font")
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
        manifest = {"format": "darksun-view-layout-reflow", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v68b"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[site, site + len(original)] for _, site, original, _ in SITES],
                "overlay_index": 48,
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"exp": "moved onto level's row: (x=149,y=120) -> (x=199,y=113)",
                "psi": "moved onto HP's row (label + number): (x=149/189,y=134) -> (x=230/270,y=127)",
                "class_names": "single-class only (e.g. GERAKIS's 角鬥士), matching v68b's scope -- "
                    "multiclass (K'RATCHEK/CERMAK/CILLA) shows English class names; see re_93 for why "
                    "the 2-/3-class draw paths are not redirected in this candidate",
                "hp_ac_dam_level_class_position": "unchanged -- already on their target rows/columns"},
            "preserved_parent_files": preserved}
        (build / "build-view-layout-reflow-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V70-READ-ME.txt").write_text(
            "v70: bottom panel reflowed from 6 rows to 4 -- class name(s) full\n"
            "width, then level+EXP, HP+PSI, and AC+DAM each sharing one row as\n"
            "left/right columns, per the user's own mockup. Only EXP and PSI\n"
            "actually moved; class/level/HP/AC/DAM were already on their target\n"
            "rows.\n"
            "Built on v68b (not v68c): live testing surfaced a pre-existing bug\n"
            "(re_93) where multiclass characters' class names all alias the last-\n"
            "decoded slot's glyphs. Rather than ship broken/garbled multiclass\n"
            "names, this candidate keeps only v68b's validated single-class\n"
            "translation; multiclass characters show English class names.\n"
            "Runtime validation NOT performed by this script.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V68B_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
