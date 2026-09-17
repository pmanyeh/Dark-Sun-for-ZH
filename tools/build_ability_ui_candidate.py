#!/usr/bin/env python3
"""Build isolated v57 inventory ability labels, retaining v56 backpack support."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import struct
import tempfile

try:
    from .build_backpack_ui_candidate import ROOT, DEFAULT_OUTPUT as V56_ROOT, sha256
    from .build_name_slot_candidate_from_v33 import run
    from .cjk_localization_pipeline import (DEFAULT_GFF_CAT, load_mapping, update_mapping,
        read_bank, glyph_record_for_id, build_bank, rasterizer, verify_extracted_gff_chunks)
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache
    from .audit_inventory_ui import TextBlock, V55_LAYOUT, layout_issues
except ImportError:
    from build_backpack_ui_candidate import ROOT, DEFAULT_OUTPUT as V56_ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from cjk_localization_pipeline import (DEFAULT_GFF_CAT, load_mapping, update_mapping,
        read_bank, glyph_record_for_id, build_bank, rasterizer, verify_extracted_gff_chunks)
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache
    from audit_inventory_ui import TextBlock, V55_LAYOUT, layout_issues

LABELS = ("力量", "敏捷", "體質", "智力", "智慧", "魅力")
V56_EXE_HASH = "e972af58edc0936fe7510cd442a9b67a5747d3f73aa78ea6ea45386d780e91a2"
V56_FONT_HASH = "883bf40550c4113f98cf900e7eb12df8cf636e959ad4ca2f89124ed9896d2aaf"
V56_RESOURCE_HASH = "8d924107807992a1c711e52c0d5fd6989db3ede698b06fe2762f926b0a5a71de"
FUSION_HASH = "ade6c9bd5b7bbe2e2bb71d66b0d3e60ccc27e89ae6972d80f2c7d949a48e33ed"
DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v57_ability_labels"
LOOP_OFFSET = 0x65125
LOOP_ORIGINAL = bytes.fromhex(
    "8B DE C1 E3 02 66 FF B7 F2 0E FF 36 70 32 6A 14 FF 36 6E 32 "
    "66 68 FF 00 FE 00 6A 00 1E 68 11 0E 8B C6 6B C0 07 8B 56 0C "
    "03 D0 52 FF 76 0A 66 FF 76 06"
)


def ability_redirect() -> bytes:
    # Capture the actual overlay IP with call/pop; do not assume a load segment
    # or add an overlay operand to the main MZ relocation table.
    result = bytes.fromhex("0E E8 00 00 58 05") + struct.pack("<H", len(LOOP_ORIGINAL) - 4)
    result += bytes.fromhex("50 B8 ED FF 8C DB 80 EF 10 53 68 14 07 CB")
    if len(result) > len(LOOP_ORIGINAL):
        raise AssertionError("ability redirect does not fit")
    return result.ljust(len(LOOP_ORIGINAL), b"\x90")


PATCHES = {
    LOOP_OFFSET: (LOOP_ORIGINAL, ability_redirect()),
    0x6F5A0: (bytes.fromhex("66 68 EC 00 17 00"), bytes.fromhex("66 68 EC 00 08 00")),
    0x6F5E7: (bytes.fromhex("6B C0 07 05 17 00"), bytes.fromhex("6B C0 0A 05 08 00")),
    0x6F5EE: (bytes.fromhex("68 04 01"), bytes.fromhex("68 08 01")),
}
V57_LAYOUT = (TextBlock("abilities", 8, 6, 10, 10),) + V55_LAYOUT[1:]


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != V56_EXE_HASH:
        raise ValueError("source EXE is not v56")
    if layout_issues(V57_LAYOUT):
        raise ValueError("v57 vertical layout does not fit")
    result = bytearray(image)
    for offset, (before, after) in PATCHES.items():
        if image[offset:offset + len(before)] != before or len(before) != len(after):
            raise ValueError(f"patch signature/size differs at {offset:X}")
        result[offset:offset + len(before)] = after
    allowed = {i for offset, (before, _) in PATCHES.items() for i in range(offset, offset + len(before))}
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, result))):
        raise AssertionError("EXE changed outside reviewed ranges")
    return bytes(result)


def extend_bank(mapping: dict, original: bytes, font_path: Path) -> tuple[dict, bytes, tuple[int, ...], list[str]]:
    if sha256(font_path.read_bytes()) != FUSION_HASH:
        raise ValueError("Fusion font differs from v55 glyph source")
    old = {e["character"]: e["id"] for e in mapping["entries"]}
    candidate = update_mapping(mapping, Counter("".join(LABELS)), [])
    ids = {e["character"]: e["id"] for e in candidate["entries"]}
    if any(ids[c] != value for c, value in old.items()):
        raise ValueError("mapping changed an existing ID")
    added = [c for c in ids if c not in old]
    if any(ids[c] // 256 != 5 for c in added):
        raise ValueError("new glyphs no longer fit existing sixth bank")
    source = read_bank(original, 5)
    render = rasterizer(font_path, 10, 10, 10, 10, 64, "pixel-aligned", True, False)
    entries = [e for e in candidate["entries"] if e["bank"] == 5]
    if [e["index"] for e in entries] != list(range(len(entries))):
        raise ValueError("C5 must retain dense indexing for the DOS loader")

    def preserve_or_render(char):
        if char in old:
            record = source["records"][old[char] % 256]
            return 10, record[2:]
        width, pixels = render(char)
        if width != 10 or not any(value == 0xFE for value in pixels):
            raise ValueError(f"invalid/empty new glyph: {char}")
        return width, pixels

    payload = build_bank(5, entries, 10, preserve_or_render)
    final = read_bank(payload, 5)
    for index, record in source["records"].items():
        if final["records"][index] != record:
            raise ValueError("existing C5 glyph changed")
    return candidate, payload, tuple(ids[c] for c in "".join(LABELS)), added


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v56")
    game = source / "GAME/DARKSUN"
    original_exe = (game / "DSUN.EXE").read_bytes()
    original_resource = (game / "RESOURCE.GFF").read_bytes()
    if sha256(original_resource) != V56_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v56")
    exe = patch_executable(original_exe)
    mapping, c5, ids, added = extend_bank(load_mapping(ROOT / "localization/cjk_mapping.json"),
        (game / "C5").read_bytes(), ROOT / "Fonts/Fusion_Pixel_10px.ttf")
    banks = {i: read_bank(c5 if i == 5 else (game / f"C{i}").read_bytes(), i) for i in range(6)}
    for value in ids:
        if len(glyph_record_for_id(value, banks)) != 102:
            raise ValueError("ability glyph is not 10x10")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-ui-v57-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"
        path = work / "font.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", path)
        font = path.read_bytes()
        if sha256(font) != V56_FONT_HASH or font[FONT_CORE_PAYLOAD_OFFSET:] != assemble_name_slot_cache(backpack_ids=(1303, 100)):
            raise ValueError("v56 FONT/core is not reproducible")
        # Two 10px glyphs plus the native colon must leave room before X=264.
        colon_index = font[8 + ord(":")]
        colon_offset = struct.unpack_from("<H", font, 0x108 + colon_index * 2)[0]
        colon_width = struct.unpack_from("<H", font, colon_offset)[0]
        if 236 + 20 + colon_width > 264:
            raise ValueError("Chinese label collides with ability number")
        font = font[:FONT_CORE_PAYLOAD_OFFSET] + assemble_name_slot_cache(backpack_ids=(1303, 100), ability_ids=ids)
        path.write_bytes(font)
        (target / "DSUN.EXE").write_bytes(exe)
        (target / "C5").write_bytes(c5)
        run(DEFAULT_GFF_CAT, "replace", game / "RESOURCE.GFF", "FONT", "100", path, "-o", target / "RESOURCE.GFF")
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "--all", "-o", work / "before")
        run(DEFAULT_GFF_CAT, "extract", target / "RESOURCE.GFF", "--all", "-o", work / "after")
        verification = verify_extracted_gff_chunks(work / "before", work / "after", [
            {"kind": "FONT", "chunk_id": 100, "sha256": sha256(font), "encoded_byte_length": len(font)}])
        preserved = 0
        for old_path in source.rglob("*"):
            rel = old_path.relative_to(source)
            if old_path.is_file() and rel.as_posix() not in {"GAME/DARKSUN/DSUN.EXE", "GAME/DARKSUN/RESOURCE.GFF", "GAME/DARKSUN/C5"}:
                if old_path.read_bytes() != (build / rel).read_bytes():
                    raise ValueError(f"unexpected file difference: {rel}")
                preserved += 1
        manifest = {"format": "darksun-ability-ui-candidate", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v56_backpack_user_confirmed"},
            "parent": {"root": str(source), "exe_sha256": sha256(original_exe), "resource_sha256": sha256(original_resource)},
            "executable": {"sha256": sha256(exe), "patch_ranges": [[o, o + len(p[0])] for o, p in PATCHES.items()], "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "ability_ids": ids, "colon_width": colon_width},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "bank5": {"sha256": sha256(c5), "bytes": len(c5), "new_characters": added, "existing_records_unchanged": True},
            "labels": LABELS, "layout": {"label_x": 236, "number_x": 264, "y": [8, 18, 28, 38, 48, 58], "weapon_origin": 99, "weapon_last_pixel": 168},
            "preserved_parent_files": preserved,
            "mapping_policy": "candidate-local append-only IDs; root catalog and mapping unchanged"}
        (build / "build-ability-ui-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "cjk-mapping-v57.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V57-READ-ME.txt").write_text("v57: six Chinese inventory ability labels. Runtime validation NOT performed.\nUse build-ability-ui-manifest.json; older manifests describe ancestors.\n", encoding="ascii")
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V56_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
