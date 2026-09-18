#!/usr/bin/env python3
"""Build v73: second row-spacing pass -- v72 overcorrected.

v72 (see re_95) fixed the cramped 7px gap between the class-name row and
the level+EXP row by pushing level/EXP, HP+PSI and AC+DAM all down/up
fairly aggressively (gaps 13/9/9). Live review on the user's own machine
showed this went too far the other way: the class/level gap became
comfortable, but HP+PSI and AC+DAM ended up looking stuck together again
(9px is too tight for these two heavier lines -- EXP's parenthesised
threshold number and the DAM dice expression are both visually denser
than a plain two-column stat row).

User's own instruction after seeing v72 live: move the level+EXP and
HP+PSI rows up a bit (closer to the class-name row, but not touching it),
and specifically open up more space between HP+PSI and AC+DAM. New Y
positions (v72 -> v73):
    class name   106 -> 106   (unchanged -- still the same overlay
                                relocation conflict from v72, see its
                                own docstring)
    level/EXP    119 -> 115   (gap from class name: 13 -> 9)
    HP+PSI       128 -> 125   (gap from level/EXP: 9 -> 10)
    AC+DAM       137 -> 138   (gap from HP+PSI: 9 -> 13)

Same six overlay-48 position sites as v72 (`build_view_layout_adjust_candidate.py`),
same reasoning for why the class-name row itself is excluded. The HP:/PSI:
label Y (FONT-local `.long` constants) moves the same way as the number Y,
directly in `cjk_name_slot_cache.asm`.
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

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v73_view_layout_adjust2"
V72_ROOT = ROOT / "scratch_test/cjk_display_staging_v72_view_layout_adjust"
PARENT_EXE_HASH = "03fc791356cdd1a6b1f583ca315f1d3937c4cf726f41d599765311a5af13362b"
PARENT_RESOURCE_HASH = "6ebcd702badab114969cfa5f7341c8d7e59f7925374a7825b838432b0078400e"
PARENT_FONT_HASH = "f50e5ebce58e52679cbaab42ef79a1f90001e2b9d62d13f0903e3244c1a33d16"

# Same six overlay-48 sites v72 patches; class name (0x8A1E4) stays out for
# the same overlay-relocation reason documented in v72's own build script.
LEVEL_SITE = 0x8A214
LEVEL_ORIGINAL = bytes.fromhex("666895007700")  # x=149, y=119
LEVEL_NEW = bytes.fromhex("666895007300")        # x=149, y=115

EXP_SITE = 0x8A281
EXP_ORIGINAL = bytes.fromhex("6668C7007700")  # x=199, y=119
EXP_NEW = bytes.fromhex("6668C7007300")        # x=199, y=115

HP_NUMBER_SITE = 0x8A2CF
HP_NUMBER_ORIGINAL = bytes.fromhex("6668BD008000")  # x=189, y=128
HP_NUMBER_NEW = bytes.fromhex("6668BD007D00")        # x=189, y=125

PSI_NUMBER_SITE = 0x8A345
PSI_NUMBER_ORIGINAL = bytes.fromhex("66680E018000")  # x=270, y=128
PSI_NUMBER_NEW = bytes.fromhex("66680E017D00")        # x=270, y=125

DEF_SITE = 0x8A38C
DEF_ORIGINAL = bytes.fromhex("666895008900")  # x=149, y=137
DEF_NEW = bytes.fromhex("666895008A00")        # x=149, y=138

DAM_SITE = 0x8A3C1
DAM_ORIGINAL = bytes.fromhex("6668C7008900")  # x=199, y=137
DAM_NEW = bytes.fromhex("6668C7008A00")        # x=199, y=138

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
        raise ValueError("source EXE is not v72")
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
        raise ValueError("output must be a new directory outside v72")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v72")
    patched = patch_executable(exe)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-layout-adjust2-v73-", dir=output.parent) as temporary:
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
            raise ValueError("v72 FONT does not match the reviewed pre-adjust font")
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
        manifest = {"format": "darksun-view-layout-adjust2", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v72"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[site, site + len(original)] for _, site, original, _ in SITES],
                "overlay_index": 48,
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"rows": "class name Y unchanged at 106 (overlay relocation conflict, "
                    "same as v72), level/EXP Y 119->115, HP+PSI Y 128->125, AC+DAM Y 137->138 "
                    "-- gaps now class/level=9, level/HP=10, HP/DAM=13 (v72 had 13/9/9, "
                    "which the user found HP+PSI/AC+DAM too cramped)"},
            "preserved_parent_files": preserved}
        (build / "build-view-layout-adjust2-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V73-READ-ME.txt").write_text(
            "v73: second row-spacing pass on the bottom panel. v72 over-\n"
            "corrected -- class/level gap became comfortable but HP+PSI and\n"
            "AC+DAM ended up stuck together. This candidate moves level/EXP\n"
            "and HP+PSI back up a little (closer to, but not touching, the\n"
            "class-name row) and gives HP+PSI/AC+DAM noticeably more room.\n"
            "Built on v72 (multiclass class names, 10-slot pool, and the\n"
            "Preserver/Thri-kreen terminology fixes all carried over\n"
            "unchanged). Runtime validation NOT performed by this script.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V72_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
