#!/usr/bin/env python3
"""Build v63: three-column VIEW CHARACTER ability grid + equipment-slot revert.

v58b moved the three equipment-slot APFM placements (2BCFh/2BD0h/2BD1h) and
v59 relocated five hidden placeholder APFM placements (2BD6h/2BDBh/2BDCh/
2BDDh/2BDEh) inside the shared WIND-11500 resource. Both sets of controls are
also read by other screens (e.g. USE), so moving them there moved icons on
those other screens too. This candidate restores all eight WIND-11500 APFM
records verbatim from v57 (before either change), undoing that regression.

Independently, the six-ability grid is reflowed from two columns of three
rows into three columns of two rows (STR/DEX/CON on top, INT/WIS/CHA below).
This is a FONT-local coordinate change only (`view_coordinates` in
cjk_name_slot_cache.asm); the EXE is carried over from v61 unmodified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

try:
    from .build_ability_ui_candidate import DEFAULT_OUTPUT as V57_ROOT, LABELS
    from .build_backpack_ui_candidate import ROOT, sha256
    from .build_fixed_labels_candidate import DEFAULT_OUTPUT as V61_ROOT, LABEL_IDS
    from .build_name_slot_candidate_from_v33 import run
    from .cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache
except ImportError:
    from build_ability_ui_candidate import DEFAULT_OUTPUT as V57_ROOT, LABELS
    from build_backpack_ui_candidate import ROOT, sha256
    from build_fixed_labels_candidate import DEFAULT_OUTPUT as V61_ROOT, LABEL_IDS
    from build_name_slot_candidate_from_v33 import run
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v63_view_ability_regrid"
PARENT_EXE_HASH = "3c56a1a724e1de0e0656a91c96a088cf6bd15b453e0f83a21315bd3d0653b879"
PARENT_RESOURCE_HASH = "fbfd002aa42b43a76dfaed473b8de35dac802a5220d7d48ec9bb162025a2abba"
# v61's own FONT-100, built from the *pre-regrid* two-column view_coordinates.
# The shared asm source is edited in place for this candidate, so the parent
# font can no longer be re-derived by reassembling it -- check its hash instead.
PARENT_FONT_HASH = "151a5801d2bfb4956d9b6d697bbd2403ccf250119145536130080a0346ac25ee"
PRISTINE_WIND_ROOT = V57_ROOT
# The three real equipment slots occupy y=42..60 now that they are back at
# their original horizontal row, so the ability grid's top row must start
# clear of that band (unlike v61's view_y_origin=43, chosen back when the
# slots were out of the way in their own vertical column at x=259).
VIEW_Y_ORIGIN = 63


def coordinates(row: int) -> tuple[int, int, int]:
    """Expected (label_x, number_x, y) for ability row 0..5 under v63's
    three-columns-by-two-rows layout (STR/DEX/CON on top, INT/WIS/CHA
    below), with the equipment-clearing y_origin defined above."""
    if not 0 <= row < 6:
        raise ValueError("ability row outside 0..5")
    x = 149 + 44 * (row % 3)
    return x, x + 28, VIEW_Y_ORIGIN + 12 * (row // 3)


# The eight APFM records v58b/v59 moved, restored to these v57 coordinates.
REVERTED_PLACEMENTS = {
    0x2BCF: (205, 42), 0x2BD0: (224, 42), 0x2BD1: (243, 42),
    0x2BD6: (243, 62), 0x2BDB: (243, 82),
    0x2BDC: (262, 42), 0x2BDD: (262, 62), 0x2BDE: (262, 82),
}


def revert_window(pristine: bytes, current: bytes) -> bytes:
    if pristine[:4] != b"WIND" or len(pristine) != 2841:
        raise ValueError("pristine WIND-11500 does not match the reviewed v57 window")
    if current[:4] != b"WIND" or len(current) != len(pristine):
        raise ValueError("current WIND-11500 differs in shape from v57")
    import struct
    for ident, expected in REVERTED_PLACEMENTS.items():
        marker = b"APFM" + struct.pack("<I", ident)
        if pristine.count(marker) != 1:
            raise ValueError(f"missing/ambiguous pristine APFM placement {ident:04X}")
        offset = pristine.index(marker) + 8
        if struct.unpack_from("<hh", pristine, offset) != expected:
            raise ValueError(f"pristine APFM {ident:04X} is not at the expected v57 coordinates")
    # Every byte outside the eight reverted APFM coordinate pairs must still
    # match between v57 and the current (v61) window, i.e. nothing else in
    # this resource has drifted since v57.
    touched: set[int] = set()
    for ident in REVERTED_PLACEMENTS:
        marker = b"APFM" + struct.pack("<I", ident)
        offset = pristine.index(marker) + 8
        touched.update(range(offset, offset + 4))
    for i, (a, b) in enumerate(zip(pristine, current)):
        if i not in touched and a != b:
            raise ValueError(f"unexpected WIND-11500 drift outside reverted APFM fields at 0x{i:X}")
    return pristine


def build_candidate(source: Path, pristine_source: Path, output: Path) -> dict:
    source, pristine_source, output = source.resolve(), pristine_source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v61")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(exe) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v61")
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v61")
    mapping = load_mapping(source / "cjk-mapping-v57.json")
    by_char = {entry["character"]: entry["id"] for entry in mapping["entries"]}
    ability_ids = tuple(by_char[c] for c in "".join(LABELS))
    base_options = dict(backpack_ids=(1303, 100), ability_ids=ability_ids, view_character=True, view_y_origin=VIEW_Y_ORIGIN)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-ability-regrid-v63-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"
        font_path, wind_path, pristine_wind_path = work / "font.bin", work / "wind.bin", work / "pristine_wind.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "WIND", "11500", "-o", wind_path)
        run(DEFAULT_GFF_CAT, "extract", pristine_source / "GAME/DARKSUN/RESOURCE.GFF", "WIND", "11500", "-o", pristine_wind_path)
        original_font = font_path.read_bytes()
        if sha256(original_font) != PARENT_FONT_HASH:
            raise ValueError("v61 FONT does not match the reviewed pre-regrid font")
        font = original_font[:FONT_CORE_PAYLOAD_OFFSET] + assemble_name_slot_cache(**base_options, label_ids=LABEL_IDS)
        window = revert_window(pristine_wind_path.read_bytes(), wind_path.read_bytes())
        font_path.write_bytes(font)
        wind_path.write_bytes(window)
        (target / "DSUN.EXE").write_bytes(exe)
        run(DEFAULT_GFF_CAT, "replace", game / "RESOURCE.GFF", "FONT", "100", font_path, "-o", work / "font.gff")
        run(DEFAULT_GFF_CAT, "replace", work / "font.gff", "WIND", "11500", wind_path, "-o", target / "RESOURCE.GFF")
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "--all", "-o", work / "before")
        run(DEFAULT_GFF_CAT, "extract", target / "RESOURCE.GFF", "--all", "-o", work / "after")
        verification = verify_extracted_gff_chunks(work / "before", work / "after", [
            {"kind": k, "chunk_id": i, "sha256": sha256(b), "encoded_byte_length": len(b)}
            for k, i, b in (("FONT", 100, font), ("WIND", 11500, window))])
        preserved = 0
        for path in source.rglob("*"):
            rel = path.relative_to(source)
            if path.is_file() and rel.as_posix() not in {"GAME/DARKSUN/DSUN.EXE", "GAME/DARKSUN/RESOURCE.GFF"}:
                if path.read_bytes() != (build / rel).read_bytes():
                    raise ValueError(f"unexpected copied file difference: {rel}")
                preserved += 1
        manifest = {"format": "darksun-view-ability-regrid", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v61"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(exe), "unchanged_from_parent": True},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": LABEL_IDS},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "window": {"sha256": sha256(window), "reverted_placements": REVERTED_PLACEMENTS,
                "note": "byte-identical to v57's pristine WIND-11500"},
            "layout": {"ability_grid": "3 columns x 2 rows (STR/DEX/CON row 0, INT/WIS/CHA row 1)",
                "equipment_slots": "reverted to original v57 horizontal row",
                "lower_panel_gender_race_alignment_class_exp_hp_psi": "unchanged, still pending"},
            "preserved_parent_files": preserved}
        (build / "build-view-ability-regrid-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V63-READ-ME.txt").write_text(
            "v63: VIEW CHARACTER ability grid reflowed to 3 columns x 2 rows;\n"
            "the three equipment slots and five hidden placeholder controls in\n"
            "WIND-11500 are restored to their original v57 coordinates, fixing the\n"
            "v58b/v59 regression that also moved icons on the USE screen.\n"
            "Gender/race/alignment/class/EXP/HP/PSI lower-panel translation is a\n"
            "separate, not-yet-started phase. Runtime validation NOT performed.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V61_ROOT)
    parser.add_argument("--pristine-source", type=Path, default=PRISTINE_WIND_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.pristine_source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
