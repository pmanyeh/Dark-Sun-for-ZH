#!/usr/bin/env python3
"""Build v74: pull EXP and PSI (label+number) left, closer to the level/HP columns.

Per the user's own annotated screenshot on v73: EXP (on the level row) and
the PSI label+number (on the HP row) sit noticeably far right of the
content immediately to their left (the level digits, and 生命:NN/NN
respectively), leaving an oversized gap. First attempt pulled both left by
25px, which the user caught live as overshooting -- "2/2/3" and "EXP:",
and "15/15" and "靈能:", started overlapping. This is the corrected,
smaller pass:

    EXP number/threshold   X=199 -> 187   (-12)
    PSI label ("靈能:")     X=230 -> 218   (-12)
    PSI number ("NN/NN")    X=270 -> 258   (-12)

PSI's label and number move by the same -12 so the 40px gap between them
(unchanged since re_89/re_93) is preserved -- only their shared starting
point shifts left. EXP is a single already-formatted string (re_93: "EXP
括號、HP／PSI 比值與傷害式都取自遊戲已格式化的輸出"), so it only has the
one position to move.

Same overlay-48 EXE-immediate mechanism as every prior row/column
adjustment (v70/v72/v73); the PSI label's X lives in the FONT-local
`.long` constant `view_psi_decoded` uses (re_89's tag redirect), not an
EXE site.

This candidate does not touch Y (row) positions at all -- v73's row
spacing stands unchanged.
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

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v74_view_column_shift"
V73_ROOT = ROOT / "scratch_test/cjk_display_staging_v73_view_layout_adjust2"
PARENT_EXE_HASH = "d0e46120bbbc14111e5e51c754c117e577beb3150c07b3eb3562709e42b1ac93"
PARENT_RESOURCE_HASH = "647c9c22463cb4f4787a91ec031127817d14298a8ca9f6f252ceb5778225b56f"
PARENT_FONT_HASH = "1f66a8c8b1c5750d0750f681d71596f58d923b613a46517119439d1b76de35de"

# Both sites confirmed inside overlay 48 (file_start=0x89E70), same as
# every prior row-position candidate. Y is unchanged from v73; only X moves.
# First attempt at this shift (-25px) overlapped the level digits / 生命
# text (confirmed live -- the user caught it immediately) -- this is a
# smaller, more conservative -12px pass instead.
EXP_SITE = 0x8A281
EXP_ORIGINAL = bytes.fromhex("6668C7007300")  # x=199, y=115
EXP_NEW = bytes.fromhex("6668BB007300")        # x=187, y=115

PSI_NUMBER_SITE = 0x8A345
PSI_NUMBER_ORIGINAL = bytes.fromhex("66680E017D00")  # x=270, y=125
PSI_NUMBER_NEW = bytes.fromhex("666802017D00")        # x=258, y=125

SITES = [
    ("exp_position", EXP_SITE, EXP_ORIGINAL, EXP_NEW),
    ("psi_number_position", PSI_NUMBER_SITE, PSI_NUMBER_ORIGINAL, PSI_NUMBER_NEW),
]


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v73")
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
        raise ValueError("output must be a new directory outside v73")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v73")
    patched = patch_executable(exe)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-column-shift-v74-", dir=output.parent) as temporary:
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
            raise ValueError("v73 FONT does not match the reviewed pre-shift font")
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
        manifest = {"format": "darksun-view-column-shift", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v73"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[site, site + len(original)] for _, site, original, _ in SITES],
                "overlay_index": 48,
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"columns": "EXP X 199->187, PSI label+number X 230/270 -> 218/258 "
                    "(both -12, gap between them unchanged); Y positions untouched from v73"},
            "preserved_parent_files": preserved}
        (build / "build-view-column-shift-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V74-READ-ME.txt").write_text(
            "v74: pulls EXP and PSI (label+number) left by 12px each, closer\n"
            "to the level digits / 生命:NN/NN content on their own rows, per\n"
            "the user's own annotated v73 screenshot (an initial -25px pass\n"
            "overshot into overlap, caught live and corrected). Row (Y)\n"
            "positions are unchanged from v73. Built on v73 (all prior fixes\n"
            "carried over unchanged). Runtime validation NOT performed by\n"
            "this script.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V73_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
