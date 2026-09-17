#!/usr/bin/env python3
"""Build v58: independent two-column VIEW CHARACTER ability layout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
import runpy

try:
    from .build_ability_ui_candidate import DEFAULT_OUTPUT as V57_ROOT, LABELS
    from .build_backpack_ui_candidate import ROOT, sha256
    from .build_name_slot_candidate_from_v33 import run
    from .cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache
except ImportError:
    from build_ability_ui_candidate import DEFAULT_OUTPUT as V57_ROOT, LABELS
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v58b_view_character_columns"
V57_EXE_HASH = "740d0d797556c05a152baecf7e7124de13c39a0ad3e7ea8b392aaf5419643a6b"
V57_RESOURCE_HASH = "447a52d36a0160c3b515539f1dce91dba7af8bd18ff9c5d65aeda93bf0fde23b"
V57_FONT_HASH = "cafdbf59e222a5876dca94e0b95bb936c864e75cab060df738871d1eefebe184"
LABEL_SITE = 0x8A0E8
NUMBER_SITE = 0x8A149
LABEL_ORIGINAL = bytes.fromhex(
    "8B DE C1 E3 02 66 FF B7 F2 0E FF 36 70 32 6A 14 FF 36 6E 32 "
    "66 68 FF 00 FE 00 6A 00 1E 68 51 33 8B C6 6B C0 07 05 28 00 "
    "50 68 95 00")
NUMBER_ORIGINAL = bytes.fromhex("FF 36 70 32 6A 14 FF 36 6E 32 66 68 FF 00 FE 00 6A 00 1E 68 5A 33 8B C6 6B C0 07 05 28 00 50 68 AD 00")
PLACEMENTS = {0x2BCF: ((205, 42), (259, 42)),
              0x2BD0: ((224, 42), (259, 61)),
              0x2BD1: ((243, 42), (259, 80))}


def redirect(size: int, tag: int) -> bytes:
    result = bytes.fromhex("0E E8 00 00 58 05") + struct.pack("<H", size - 4)
    result += b"\x50\xB8" + struct.pack("<H", tag) + bytes.fromhex("8C DB 80 EF 10 53 68 14 07 CB")
    if size < len(result):
        raise ValueError("redirect site is too short")
    return result.ljust(size, b"\x90")


def coordinates(row: int) -> tuple[int, int, int]:
    """Expected (label_x, number_x, y) for ability row 0..5.

    v58b/v59 laid this out as two columns of three rows. v63 reflowed the
    shared `view_coordinates` asm to three columns of two rows (STR/DEX/CON
    on top, INT/WIS/CHA below), so this now tracks the layout the asm
    actually produces; every test file that imports this name (directly, or
    via `shifted_coordinates`) checks against current behavior, not v58b's.
    """
    if not 0 <= row < 6:
        raise ValueError("ability row outside 0..5")
    x = 149 + 44 * (row % 3)
    return x, x + 28, 40 + 12 * (row // 3)


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != V57_EXE_HASH:
        raise ValueError("source EXE is not v57")
    result = bytearray(image)
    ranges = ((LABEL_SITE, LABEL_ORIGINAL, 0xFFEC), (NUMBER_SITE, NUMBER_ORIGINAL, 0xFFEB))
    verify_overlay_relocations(image, [(o, o + len(b)) for o, b, _ in ranges])
    for offset, original, tag in ranges:
        if image[offset:offset + len(original)] != original:
            raise ValueError(f"view loop mismatch at {offset:X}")
        result[offset:offset + len(original)] = redirect(len(original), tag)
    allowed = {i for offset, original, _ in ranges for i in range(offset, offset + len(original))}
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, result))):
        raise AssertionError("unexpected EXE difference")
    return bytes(result)


def verify_overlay_relocations(image: bytes, ranges: list[tuple[int, int]]) -> None:
    """Conservatively reject touching either byte of a Borland overlay fixup."""
    parser = runpy.run_path(str(ROOT / "vendor/opends/tools/ovr-map/ovr-map.py"))
    mz = parser["parse_mz"](image)
    fbov = parser["parse_fbov"](image, mz["image_end"])
    start = parser["find_table"](image, fbov["exeinfo"], mz["image_end"])
    segments = parser["parse_table"](image, start, mz["image_end"], fbov["overlay_base"])
    for segment in segments:
        relevant = [(a, b) for a, b in ranges if a < segment["file_end"] and b > segment["file_start"]]
        if not relevant:
            continue
        count = segment["relocation_count"]
        offsets = struct.unpack_from(f"<{count}H", image, segment["file_end"])
        for offset in offsets:
            site = segment["file_start"] + offset
            if any(a < site + 2 and b > site for a, b in relevant):
                raise ValueError(f"patch overlaps overlay relocation at 0x{site:X}")


def patch_window(window: bytes) -> bytes:
    if window[:4] != b"WIND" or len(window) != 2841 or struct.unpack_from("<I", window, 8)[0] != 11500:
        raise ValueError("not the reviewed VIEW CHARACTER WIND-11500")
    result = bytearray(window)
    for ident, (before, after) in PLACEMENTS.items():
        marker = b"APFM" + struct.pack("<I", ident)
        if window.count(marker) != 1:
            raise ValueError(f"missing/ambiguous APFM placement {ident}")
        offset = window.index(marker) + 8
        if struct.unpack_from("<hh", window, offset) != before:
            raise ValueError(f"APFM coordinates differ for {ident}")
        struct.pack_into("<hh", result, offset, *after)
    return bytes(result)


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v57")
    game = source / "GAME/DARKSUN"
    exe = (game / "DSUN.EXE").read_bytes()
    resource = (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != V57_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v57")
    patched = patch_executable(exe)
    mapping = load_mapping(source / "cjk-mapping-v57.json")
    by_char = {e["character"]: e["id"] for e in mapping["entries"]}
    ids = tuple(by_char[c] for c in "".join(LABELS))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-character-v58-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"
        font_path, wind_path = work / "font.bin", work / "wind.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "WIND", "11500", "-o", wind_path)
        font = font_path.read_bytes()
        if sha256(font) != V57_FONT_HASH or font[FONT_CORE_PAYLOAD_OFFSET:] != assemble_name_slot_cache(backpack_ids=(1303, 100), ability_ids=ids):
            raise ValueError("v57 FONT/core mismatch")
        font = font[:FONT_CORE_PAYLOAD_OFFSET] + assemble_name_slot_cache(backpack_ids=(1303, 100), ability_ids=ids, view_character=True)
        window = patch_window(wind_path.read_bytes())
        font_path.write_bytes(font)
        wind_path.write_bytes(window)
        (target / "DSUN.EXE").write_bytes(patched)
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
        manifest = {"format": "darksun-view-character-columns", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v57"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched), "patch_ranges": [[LABEL_SITE, LABEL_SITE + len(LABEL_ORIGINAL)], [NUMBER_SITE, NUMBER_SITE + len(NUMBER_ORIGINAL)]], "main_mz_relocations_added": 0, "overlay_surface_segment_operands_preserved": True},
            "font": {"sha256": sha256(font), "bytes": len(font)},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "window": {"sha256": sha256(window), "placements": PLACEMENTS},
            "layout": {"ability_label_number_xy": [coordinates(i) for i in range(6)], "inventory_unchanged": True, "race_alignment_unchanged": True},
            "preserved_parent_files": preserved}
        (build / "build-view-character-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V58B-READ-ME.txt").write_text("v58b: VIEW CHARACTER two-column Chinese abilities and vertical equipment slots.\nOriginal relocated surface instructions preserved.\nRuntime validation NOT performed. Use build-view-character-manifest.json.\nInherited manifests and notices describe older builds.\n", encoding="ascii")
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V57_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
