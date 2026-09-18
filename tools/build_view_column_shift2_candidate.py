#!/usr/bin/env python3
"""Build v75: nudge EXP and PSI (label+number) back right by 4px.

v74 (see re_95 1.2) pulled EXP and PSI left by 12px after an initial -25px
pass overshot into overlap. Live review on v74 showed the -12px pass left
just a touch too much gap again -- the user asked for both back right by
"3~5 pixels". This candidate applies +4px to the same three X positions
v74 touched, keeping the -12px correction's overall intent (closer to the
left column than v73) while backing off slightly from v74's exact spot:

    EXP number/threshold   X=187 -> 191   (+4)
    PSI label ("靈能:")     X=218 -> 222   (+4)
    PSI number ("NN/NN")    X=258 -> 262   (+4)

Same overlay-48 EXE-immediate sites and FONT `.long` constant as every
prior EXP/PSI position candidate (v70/v72/v73/v74). No Y (row) change.
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

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v75_view_column_shift2"
V74_ROOT = ROOT / "scratch_test/cjk_display_staging_v74_view_column_shift"
PARENT_EXE_HASH = "d955ea938012467b85fee6571dbfdf292dbb7fd2d4f6fb9195be071cd57c0a46"
PARENT_RESOURCE_HASH = "d2bdee696f27b688bbb34f30d8f91df0d389b4ce2dd3747c135e7662904a602a"
PARENT_FONT_HASH = "964a6298814bb638b8db042690ce08421a543092480f78002c299ed5460dd4a6"

# Both sites confirmed inside overlay 48 (file_start=0x89E70), same as
# every prior EXP/PSI position candidate. Y is unchanged from v74/v73.
EXP_SITE = 0x8A281
EXP_ORIGINAL = bytes.fromhex("6668BB007300")  # x=187, y=115
EXP_NEW = bytes.fromhex("6668BF007300")        # x=191, y=115

PSI_NUMBER_SITE = 0x8A345
PSI_NUMBER_ORIGINAL = bytes.fromhex("666802017D00")  # x=258, y=125
PSI_NUMBER_NEW = bytes.fromhex("666806017D00")        # x=262, y=125

SITES = [
    ("exp_position", EXP_SITE, EXP_ORIGINAL, EXP_NEW),
    ("psi_number_position", PSI_NUMBER_SITE, PSI_NUMBER_ORIGINAL, PSI_NUMBER_NEW),
]


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v74")
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
        raise ValueError("column shift patch changed main MZ relocations")
    allowed: set[int] = set()
    for _, site, original, _ in SITES:
        allowed |= set(range(site, site + len(original)))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v74")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v74")
    patched = patch_executable(exe)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-column-shift2-v75-", dir=output.parent) as temporary:
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
            raise ValueError("v74 FONT does not match the reviewed pre-shift font")
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
        manifest = {"format": "darksun-view-column-shift2", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v74"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[site, site + len(original)] for _, site, original, _ in SITES],
                "overlay_index": 48,
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"columns": "EXP X 187->191, PSI label+number X 218/258 -> 222/262 "
                    "(both +4, gap between them unchanged); Y positions untouched from v73/v74"},
            "preserved_parent_files": preserved}
        (build / "build-view-column-shift2-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V75-READ-ME.txt").write_text(
            "v75: nudges EXP and PSI (label+number) back right by 4px from\n"
            "v74, per the user's live review (\"3~5 pixels\" back right).\n"
            "Row (Y) positions are unchanged from v73/v74. Built on v74 (all\n"
            "prior fixes carried over unchanged). Runtime validation NOT\n"
            "performed by this script.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V74_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
