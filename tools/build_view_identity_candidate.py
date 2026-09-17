#!/usr/bin/env python3
"""Build v64: VIEW CHARACTER gender and race translated to Chinese.

Both are per-character numeric fields (record+0x19 for gender, record+0x18
for race) in the 71-byte identity record -- not a pre-built English string,
unlike the material/name case. The shared draw function (file offset
0x64B57) reads each field, multiplies it into a small fixed English string
table, and calls the same "%C%C%C%s" formatter used everywhere else in this
game. Two zones in that function are patched:

- The race lookup (0x64BB9..0x64BCF, 22 bytes) is a single self-contained
  span with no overlay relocation inside it, so it is replaced outright
  with a tag redirect.
- The gender lookup additionally measures the English string's on-screen
  width (to position race right after it) via a helper call whose segment
  word is an overlay relocation target at 0x64B79. That call, and the
  gender string's own English-table lookup right after it, are replaced by
  a fixed Chinese-width constant plus a short jump over the untouched
  relocation word, landing on a second tag redirect (0x64B83..0x64B98)
  that stops one push earlier than the read span to reach the required
  22-byte minimum.

MUL and THRI-KREEN needed three characters (穆, 螂, 螳) with no existing
glyph. The project's root `localization/cjk_mapping.json` already lagged
three characters behind what earlier per-candidate copies actually shipped
(慧/捷/敏, appended locally by v57's build and never synced back), so this
candidate follows the same established pattern -- extend the *parent
candidate's own* mapping copy, not the root file -- to avoid colliding with
those already-deployed IDs. Only bank 5 (C5) changes; C0-C4 are verified
byte-identical to the parent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from collections import Counter

try:
    from .build_backpack_ui_candidate import ROOT, sha256
    from .build_name_slot_candidate_from_v33 import run
    from .build_view_character_candidate import verify_overlay_relocations
    from .build_view_ability_regrid_candidate import DEFAULT_OUTPUT as V63_ROOT
    from .cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, rasterizer, build_bank, update_mapping, verify_extracted_gff_chunks,
    )
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, self_relative_tag_redirect
except ImportError:
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from build_view_character_candidate import verify_overlay_relocations
    from build_view_ability_regrid_candidate import DEFAULT_OUTPUT as V63_ROOT
    from cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, rasterizer, build_bank, update_mapping, verify_extracted_gff_chunks,
    )
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, self_relative_tag_redirect

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v64_view_identity"
PARENT_EXE_HASH = "3c56a1a724e1de0e0656a91c96a088cf6bd15b453e0f83a21315bd3d0653b879"
PARENT_RESOURCE_HASH = "00ea0d417135665facb8849bed57407b5a218b6aba2628e922d0d3d38ae60581"
# v63's own FONT-100. The shared asm source is edited in place for this
# candidate (new gender/race entries), so the parent font can no longer be
# re-derived by reassembling it -- check its hash instead.
PARENT_FONT_HASH = "311e53a44851f0a0e8aeabef0e2254bca9ac48863c55dbd74d0dbef6ea6323e6"
LABELS = ("力量", "敏捷", "體質", "智力", "智慧", "魅力")

FONT_PATH = ROOT / "Fonts/Fusion_Pixel_10px.ttf"
RASTER_OPTIONS = dict(font_size=10, pixel_width=10, height=10, advance=10, threshold=64,
                       fit_mode="pixel-aligned", add_shadow=True, clamp_shadow_bottom=False)

RACE_TAG = 0xFFCC
GENDER_TAG = 0xFFCD

RACE_SITE = 0x64BB9
RACE_ORIGINAL = bytes.fromhex("c45e0a268a471898c1e0028bd866ffb7ae0eff367032")

GENDER_SITE = 0x64B68
GENDER_ORIGINAL = bytes.fromhex(
    "268a471998c1e0028bd8ffb7a60e9a4f2f000059406bc0068946fec45e0a268a471998c1e0028bd866ffb7a60eff367032"
)
GENDER_ZONE_A_LEN = 14   # width-fix + short jump over the untouched relocation word
GENDER_GAP_LEN = 13      # untouched dead code; contains the 0x64B79 overlay relocation
GENDER_ZONE_C_LEN = 22   # tag redirect
GENDER_WIDTH_PX = 24     # two 10px-wide glyphs plus a small gap; pending live confirmation

NEW_RACE_CHARACTERS = "男性女人類矮精靈半巨身穆爾螳螂"


def gender_zone_a() -> bytes:
    jump_from = GENDER_SITE + 5 + 2  # after "mov word[bp-2],WIDTH" + the short jump itself
    displacement = (GENDER_SITE + GENDER_ZONE_A_LEN + GENDER_GAP_LEN) - jump_from
    if not -128 <= displacement <= 127:
        raise ValueError("gender zone A jump does not fit a short jump")
    zone = bytes.fromhex("C746FE") + struct.pack("<h", GENDER_WIDTH_PX) + b"\xEB" + struct.pack("<b", displacement)
    return zone.ljust(GENDER_ZONE_A_LEN, b"\x90")


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v63")
    zone_a_start = GENDER_SITE
    zone_c_start = GENDER_SITE + GENDER_ZONE_A_LEN + GENDER_GAP_LEN
    if image[GENDER_SITE:GENDER_SITE + len(GENDER_ORIGINAL)] != GENDER_ORIGINAL:
        raise ValueError("gender consumer differs")
    if image[RACE_SITE:RACE_SITE + len(RACE_ORIGINAL)] != RACE_ORIGINAL:
        raise ValueError("race consumer differs")
    verify_overlay_relocations(image, [
        (zone_a_start, zone_a_start + GENDER_ZONE_A_LEN),
        (zone_c_start, zone_c_start + GENDER_ZONE_C_LEN),
        (RACE_SITE, RACE_SITE + len(RACE_ORIGINAL)),
    ])
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    result[zone_a_start:zone_a_start + GENDER_ZONE_A_LEN] = gender_zone_a()
    result[zone_c_start:zone_c_start + GENDER_ZONE_C_LEN] = self_relative_tag_redirect(GENDER_TAG, GENDER_ZONE_C_LEN)
    result[RACE_SITE:RACE_SITE + len(RACE_ORIGINAL)] = self_relative_tag_redirect(RACE_TAG, len(RACE_ORIGINAL))
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("identity patch changed main MZ relocations")
    allowed = (set(range(zone_a_start, zone_a_start + GENDER_ZONE_A_LEN))
               | set(range(zone_c_start, zone_c_start + GENDER_ZONE_C_LEN))
               | set(range(RACE_SITE, RACE_SITE + len(RACE_ORIGINAL))))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def extend_mapping_and_rebuild_bank5(parent_mapping_path: Path) -> tuple[dict, bytes, int]:
    """Return (mapping_document, new_bank5_bytes, bank5_glyph_count)."""
    mapping = load_mapping(parent_mapping_path)
    candidate = update_mapping(mapping, Counter(NEW_RACE_CHARACTERS), [])
    by_char = {e["character"]: e for e in candidate["entries"]}
    for character in "穆螂螳":
        if by_char[character]["bank"] != 5:
            raise ValueError(f"expected {character!r} to land in bank 5, got {by_char[character]['bank']}")
    render = rasterizer(FONT_PATH, **RASTER_OPTIONS)
    bank5_entries = [e for e in candidate["entries"] if e["bank"] == 5]
    payload = build_bank(5, bank5_entries, RASTER_OPTIONS["height"], render)
    return candidate, payload, len(bank5_entries)


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v63")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v63")
    patched = patch_executable(exe)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-identity-v64-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"

        mapping, bank5, bank5_count = extend_mapping_and_rebuild_bank5(source / "cjk-mapping-v57.json")
        parent_c5 = (game / "C5").read_bytes()
        for name in ("C0", "C1", "C2", "C3", "C4"):
            if sha256((game / name).read_bytes()) != sha256((source / "GAME/DARKSUN" / name).read_bytes()):
                raise AssertionError(f"unexpected pre-existing drift in parent {name}")

        by_char = {e["character"]: e["id"] for e in mapping["entries"]}
        ability_ids = tuple(by_char[c] for c in "".join(LABELS))
        label_ids = (by_char["防"], by_char["禦"], by_char["靈"], by_char["能"])
        base_options = dict(backpack_ids=(1303, 100), ability_ids=ability_ids,
            view_character=True, view_y_origin=63, identity=True)

        font_path = work / "font.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        original_font = font_path.read_bytes()
        if sha256(original_font) != PARENT_FONT_HASH:
            raise ValueError("v63 FONT does not match the reviewed pre-identity font")
        font = original_font[:FONT_CORE_PAYLOAD_OFFSET] + assemble_name_slot_cache(
            **base_options, label_ids=label_ids)
        font_path.write_bytes(font)
        (target / "DSUN.EXE").write_bytes(patched)
        (target / "C5").write_bytes(bank5)
        run(DEFAULT_GFF_CAT, "replace", game / "RESOURCE.GFF", "FONT", "100", font_path, "-o", target / "RESOURCE.GFF")
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "--all", "-o", work / "before")
        run(DEFAULT_GFF_CAT, "extract", target / "RESOURCE.GFF", "--all", "-o", work / "after")
        verification = verify_extracted_gff_chunks(work / "before", work / "after", [
            {"kind": "FONT", "chunk_id": 100, "sha256": sha256(font), "encoded_byte_length": len(font)}])
        (build / "cjk-mapping-v57.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        preserved = 0
        for path in source.rglob("*"):
            rel = path.relative_to(source)
            if path.is_file() and rel.as_posix() not in {
                "GAME/DARKSUN/DSUN.EXE", "GAME/DARKSUN/RESOURCE.GFF", "GAME/DARKSUN/C5", "cjk-mapping-v57.json",
            }:
                if path.read_bytes() != (build / rel).read_bytes():
                    raise ValueError(f"unexpected copied file difference: {rel}")
                preserved += 1
        manifest = {"format": "darksun-view-identity", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v63"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[GENDER_SITE, GENDER_SITE + GENDER_ZONE_A_LEN],
                                  [GENDER_SITE + GENDER_ZONE_A_LEN + GENDER_GAP_LEN,
                                   GENDER_SITE + GENDER_ZONE_A_LEN + GENDER_GAP_LEN + GENDER_ZONE_C_LEN],
                                  [RACE_SITE, RACE_SITE + len(RACE_ORIGINAL)]],
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "bank5": {"sha256": sha256(bank5), "glyphs": bank5_count,
                "new_characters": {c: by_char[c] for c in "穆螂螳"}},
            "scope": {"gender": "record+0x19, two-entry table (男性/女性)",
                "race": "record+0x18, eight-entry table (人類..螳螂人)",
                "alignment": "not in this candidate -- draw call turned out to be unrelated logic, needs separate investigation",
                "class_level_exp_hp_psi": "not in this candidate, still pending"},
            "preserved_parent_files": preserved}
        (build / "build-view-identity-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V64-READ-ME.txt").write_text(
            "v64: VIEW CHARACTER gender (男性/女性) and race (人類..螳螂人) translated.\n"
            "Both are per-character numeric fields, decoded via a new FONT-local\n"
            "gender/race table lookup, not a pre-built English string.\n"
            "MUL/THRI-KREEN needed three new glyphs (穆/螂/螳); only bank 5 (C5)\n"
            "changed, C0-C4 are byte-identical to the parent.\n"
            "Alignment, class, level, EXP, HP and PSI translation are NOT in this\n"
            "candidate -- alignment's call site turned out to be unrelated logic on\n"
            "closer inspection; the others were never started. Runtime validation\n"
            "NOT performed.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V63_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
