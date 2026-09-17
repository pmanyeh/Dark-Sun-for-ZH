#!/usr/bin/env python3
"""Build isolated v59: lower abilities 3px and clear overlapping equipment hit areas.

This is an interaction/layout candidate, not the remaining identity/class translation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile

try:
    from .build_view_character_candidate import DEFAULT_OUTPUT as V58_ROOT, coordinates
    from .build_ability_ui_candidate import LABELS
    from .build_backpack_ui_candidate import ROOT, sha256
    from .build_name_slot_candidate_from_v33 import run
    from .cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache
except ImportError:
    from build_view_character_candidate import DEFAULT_OUTPUT as V58_ROOT, coordinates
    from build_ability_ui_candidate import LABELS
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v59_view_interaction"
PARENT_EXE_HASH = "9ac8f29f1a9525ca7f54a768a8c5501e23d8b22812e3c28275c8e09891b61990"
PARENT_RESOURCE_HASH = "3c8291a8a4b793bb4e2c3f382142a63ec9c4744d4a67f0abc401304bb10d1fda"
PARENT_FONT_HASH = "68d7cf5894cd8f8b87846f9c9cb70748027865cc3d37cbf27e1ef29e9419ce55"
PARENT_WINDOW_HASH = "de2204d3a092eb3a7f35d7ecbe0ec2379aa2bfdf0258e246b81ea61f0c762f47"
VIEW_Y_ORIGIN = 43
ACTIVE = {0x2BCF: (259, 42), 0x2BD0: (259, 61), 0x2BD1: (259, 80)}
# Reuse the positions vacated by v58b, with clearance at X=259. Also clear
# the two remaining X=243 placeholders, whose 18px width overlaps by 2px.
# Do not alter shared APFM chunks,
# event masks, IDs, handlers, or any inventory window placements.
DISPLACED = {0x2BD6: ((243, 62), (241, 62)),
             0x2BDB: ((243, 82), (241, 82)),
             0x2BDC: ((262, 42), (205, 42)),
             0x2BDD: ((262, 62), (224, 42)),
             0x2BDE: ((262, 82), (241, 42))}


def placement_offset(window: bytes, ident: int) -> int:
    marker = b"APFM" + struct.pack("<I", ident)
    if window.count(marker) != 1:
        raise ValueError(f"missing/ambiguous APFM {ident:X}")
    return window.index(marker) + 8


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[0] + 18 and b[0] < a[0] + 18 and a[1] < b[1] + 18 and b[1] < a[1] + 18


def shifted_coordinates(row: int) -> tuple[int, int, int]:
    x, number_x, y = coordinates(row)
    return x, number_x, y + VIEW_Y_ORIGIN - 40


def patch_window(window: bytes) -> bytes:
    if sha256(window) != PARENT_WINDOW_HASH:
        raise ValueError("source WIND-11500 is not v58b")
    result = bytearray(window)
    for ident, expected in ACTIVE.items():
        if struct.unpack_from("<hh", window, placement_offset(window, ident)) != expected:
            raise ValueError("active equipment placement differs")
    for ident, (before, after) in DISPLACED.items():
        offset = placement_offset(window, ident)
        if struct.unpack_from("<hh", window, offset) != before:
            raise ValueError("inactive equipment placement differs")
        struct.pack_into("<hh", result, offset, *after)
    # Include *all* small equipment placeholders, not just the three moved ones.
    for active_id, xy in ACTIVE.items():
        for ident in range(0x2BCD, 0x2BE2):
            if ident == active_id:
                continue
            other = struct.unpack_from("<hh", result, placement_offset(window, ident))
            if overlaps(xy, other):
                raise ValueError(f"equipment {active_id:X} still overlaps {ident:X}")
    return bytes(result)


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v58b")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(exe) != PARENT_EXE_HASH or sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source EXE/RESOURCE is not v58b")
    mapping = load_mapping(source / "cjk-mapping-v57.json")
    by_char = {entry["character"]: entry["id"] for entry in mapping["entries"]}
    ids = tuple(by_char[c] for c in "".join(LABELS))
    options = dict(backpack_ids=(1303, 100), ability_ids=ids, view_character=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-interaction-v59-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"
        font_path, wind_path = work / "font.bin", work / "wind.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "WIND", "11500", "-o", wind_path)
        original_font = font_path.read_bytes()
        if sha256(original_font) != PARENT_FONT_HASH or original_font[FONT_CORE_PAYLOAD_OFFSET:] != assemble_name_slot_cache(**options):
            raise ValueError("v58b FONT/core mismatch")
        font = original_font[:FONT_CORE_PAYLOAD_OFFSET] + assemble_name_slot_cache(**options, view_y_origin=VIEW_Y_ORIGIN)
        window = patch_window(wind_path.read_bytes())
        font_path.write_bytes(font)
        wind_path.write_bytes(window)
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
            if path.is_file() and rel.as_posix() != "GAME/DARKSUN/RESOURCE.GFF":
                if path.read_bytes() != (build / rel).read_bytes():
                    raise ValueError(f"unexpected copied file difference: {rel}")
                preserved += 1
        manifest = {"format": "darksun-view-interaction-candidate", "version": 1,
            "validation": {"runtime_status": "not_run", "right_click_status": "pending", "multiclass_translation": "not_in_this_candidate"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(exe), "unchanged": True},
            "font": {"sha256": sha256(font), "bytes": len(font)},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "window": {"sha256": sha256(window), "displaced_placeholders": DISPLACED, "active_equipment_unchanged": ACTIVE},
            "layout": {"ability_label_number_xy": [shifted_coordinates(i) for i in range(6)], "inventory_unchanged": True, "identity_classes_lower_panel_unchanged": True},
            "preserved_parent_files": preserved}
        (build / "build-view-interaction-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V59-READ-ME.txt").write_text(
            "v59: VIEW CHARACTER abilities +3 native pixels; overlapping inactive equipment placeholders relocated.\n"
            "EXE, active equipment IDs/positions, handlers, inventory and class rows unchanged.\n"
            "Right-click behavior requires runtime validation. No further identity/class translation yet.\n"
            "Use build-view-interaction-manifest.json; inherited notices describe older builds.\n", encoding="ascii")
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V58_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
