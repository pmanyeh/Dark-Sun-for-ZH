#!/usr/bin/env python3
"""Build v68: VIEW CHARACTER class names (incl. multiclass) translated.

Unlike every other VIEW CHARACTER field patched so far, this one needs no
EXE code redirect at all -- gender/race/alignment/HP:/PSI: all had to
detour through a FONT-local decoder because the draw calls read a
*record field* or lived inside a lazily-loaded overlay. Class names are
different: the record only stores up to three 1-indexed class IDs
(`record+0x21..0x23`, confirmed live: GERAKIS=10 alone, K'RATCHEK=9/7/12
for its "Fighter/Druid/Psionic" display), which the draw function
(`5B7C:2DC1`, itself overlay-loaded) looks up in a plain *pointer table*
at `DS:0x1200` (stride 4, one far pointer per ID) into a shared English
string pool starting at `DS:0x128D` -- and both the table and the pool
are plain DATA sitting in the always-resident main data segment (DS was
consistently 0x4B7A across every session this project has ever traced),
not overlay content. So this candidate just overwrites that data in
place: no new FONT tag, no redirect stub, no overlay-relocation dance.

Only 8 distinct English strings are actually referenced by any of the
first 17 class IDs (the ones observed in play or structurally implied):
Cleric (IDs 1-4, always identical), Druid (5-8), Fighter (9), Gladiator
(10), Preserver (11), Psionic (12), Ranger (13-16), Thief (17). IDs
18-20 point to " MAGE"/"CLERIC"/"PSlONlC" -- oddly cased entries that
don't match anything seen in play, left completely untouched since
there's no evidence they're dead and no room budget requires touching
them.

The eight replacements were sized to fit byte-for-byte inside the
original pool's 62-byte span (ending exactly where the untouched
" MAGE" entry begins), so nothing needs to move: 牧師 (Cleric), 德魯伊
(Druid), 戰士 (Fighter), 鬥士 (Gladiator -- shortened from the fuller
角鬥士 specifically to fit this budget), 保育師 (Preserver), 靈能
(Psionic, matching the already-shipped PSI: label wording), 遊俠
(Ranger), 盜賊 (Thief). The 4-byte pointer table's 17 live entries are
rewritten to the new in-pool offsets; the segment half of every entry
(bytes 2-3, the compile-time DGROUP placeholder `0x4356` that the
loader's own MZ relocation fixes up) is left byte-for-byte identical,
so this patch adds no new relocations and disturbs none of the existing
ones.

Six new characters are needed (牧/魯/育/俠/盜/賊); all land in bank 5
(the same bank v64's race additions and v66's alignment additions used),
growing it from 44 to 50 glyphs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile
from collections import Counter

try:
    from .build_backpack_ui_candidate import ROOT, sha256
    from .build_name_slot_candidate_from_v33 import run
    from .build_view_character_candidate import verify_overlay_relocations
    from .cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, rasterizer, build_bank, update_mapping, verify_extracted_gff_chunks,
    )
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
except ImportError:
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from build_view_character_candidate import verify_overlay_relocations
    from cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, rasterizer, build_bank, update_mapping, verify_extracted_gff_chunks,
    )
    from patch_dsun_scratch_cache import mz_relocation_file_offsets

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v68_view_class_names"
V67_ROOT = ROOT / "scratch_test/cjk_display_staging_v67_view_hp_psi_labels"
PARENT_EXE_HASH = "39a18dd6e6c9c80e9a3076929cece2bdc4453c1b5950471ee2ffba7b9e4d101b"
PARENT_RESOURCE_HASH = "3520b38388cd60cf3f379a41df4707ab899989c344fc51ff21a60610b5a4f589"

FONT_PATH = ROOT / "Fonts/Fusion_Pixel_10px.ttf"
RASTER_OPTIONS = dict(font_size=10, pixel_width=10, height=10, advance=10, threshold=64,
                       fit_mode="pixel-aligned", add_shadow=True, clamp_shadow_bottom=False)

POOL_SITE = 0x49BED
POOL_LEN = 62
POOL_ORIGINAL = (b"Cleric\x00Druid\x00Fighter\x00Gladiator\x00Preserver\x00"
                 b"Psionic\x00Ranger\x00Thief\x00")

TABLE_SITE = 0x49B60
TABLE_IDS = 17  # 1..17; IDs 18-20 (" MAGE"/"CLERIC"/"PSlONlC") are untouched
TABLE_LEN = TABLE_IDS * 4
TABLE_SEGMENT_WORD = bytes.fromhex("5643")  # untouched DGROUP relocation placeholder
TABLE_ORIGINAL = bytes.fromhex(
    "8d1256438d1256438d1256438d125643"
    "941256439412564394125643941256439a125643a2125643ac125643b6125643"
    "be125643be125643be125643be125643"
    "c5125643"
)

NEW_CLASS_CHARACTERS = "牧魯育俠盜賊"


def _encode(char_id: int) -> bytes:
    return bytes([0x5E, (char_id // 94) + 0x21, (char_id % 94) + 0x21])


def build_pool_and_table(by_char: dict[str, int]) -> tuple[bytes, bytes]:
    def name(*chars: str) -> bytes:
        return b"".join(_encode(by_char[c]) for c in chars) + b"\x00"

    entries = [
        name("牧", "師"),        # Cleric
        name("德", "魯", "伊"),  # Druid
        name("戰", "士"),        # Fighter
        name("鬥", "士"),        # Gladiator (shortened from 角鬥士 to fit the budget)
        name("保", "育", "師"),  # Preserver
        name("靈", "能"),        # Psionic (matches the shipped PSI: wording)
        name("遊", "俠"),        # Ranger
        name("盜", "賊"),        # Thief
    ]
    pool = b"".join(entries)
    if len(pool) != POOL_LEN:
        raise AssertionError(f"class name pool is {len(pool)} bytes, expected {POOL_LEN}")

    offsets: list[int] = []
    pos = 0
    for entry in entries:
        offsets.append(0x128D + pos)
        pos += len(entry)
    cleric, druid, fighter, gladiator, preserver, psionic, ranger, thief = offsets

    id_offset = {}
    for i in range(1, 5):
        id_offset[i] = cleric
    for i in range(5, 9):
        id_offset[i] = druid
    id_offset[9] = fighter
    id_offset[10] = gladiator
    id_offset[11] = preserver
    id_offset[12] = psionic
    for i in range(13, 17):
        id_offset[i] = ranger
    id_offset[17] = thief

    table = b"".join(id_offset[i].to_bytes(2, "little") + TABLE_SEGMENT_WORD for i in range(1, TABLE_IDS + 1))
    if len(table) != TABLE_LEN:
        raise AssertionError("class name table length mismatch")
    return pool, table


def patch_executable(image: bytes, pool: bytes, table: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v67")
    if image[POOL_SITE:POOL_SITE + POOL_LEN] != POOL_ORIGINAL:
        raise ValueError("class name pool differs")
    if image[TABLE_SITE:TABLE_SITE + TABLE_LEN] != TABLE_ORIGINAL:
        raise ValueError("class name table differs")
    # This is plain DGROUP data, not overlay content, but the guard is cheap insurance.
    verify_overlay_relocations(image, [(POOL_SITE, POOL_SITE + POOL_LEN), (TABLE_SITE, TABLE_SITE + TABLE_LEN)])
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    result[POOL_SITE:POOL_SITE + POOL_LEN] = pool
    result[TABLE_SITE:TABLE_SITE + TABLE_LEN] = table
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("class name patch changed main MZ relocations")
    allowed = set(range(POOL_SITE, POOL_SITE + POOL_LEN)) | set(range(TABLE_SITE, TABLE_SITE + TABLE_LEN))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def extend_mapping_and_rebuild_bank5(parent_mapping_path: Path) -> tuple[dict, bytes, int]:
    mapping = load_mapping(parent_mapping_path)
    candidate = update_mapping(mapping, Counter(NEW_CLASS_CHARACTERS), [])
    by_char = {e["character"]: e for e in candidate["entries"]}
    for character in NEW_CLASS_CHARACTERS:
        if by_char[character]["bank"] != 5:
            raise ValueError(f"expected {character!r} to land in bank 5, got {by_char[character]['bank']}")
    render = rasterizer(FONT_PATH, **RASTER_OPTIONS)
    bank5_entries = [e for e in candidate["entries"] if e["bank"] == 5]
    payload = build_bank(5, bank5_entries, RASTER_OPTIONS["height"], render)
    return candidate, payload, len(bank5_entries)


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v67")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v67")

    mapping, bank5, bank5_count = extend_mapping_and_rebuild_bank5(source / "cjk-mapping-v57.json")
    by_char = {e["character"]: e["id"] for e in mapping["entries"]}
    pool, table = build_pool_and_table(by_char)
    patched = patch_executable(exe, pool, table)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-class-names-v68-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"
        for name in ("C0", "C1", "C2", "C3", "C4"):
            if sha256((game / name).read_bytes()) != sha256((source / "GAME/DARKSUN" / name).read_bytes()):
                raise AssertionError(f"unexpected pre-existing drift in parent {name}")

        (target / "DSUN.EXE").write_bytes(patched)
        (target / "C5").write_bytes(bank5)
        (build / "cjk-mapping-v57.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        preserved = 0
        for path in source.rglob("*"):
            rel = path.relative_to(source)
            if path.is_file() and rel.as_posix() not in {
                "GAME/DARKSUN/DSUN.EXE", "GAME/DARKSUN/C5", "cjk-mapping-v57.json",
            }:
                if path.read_bytes() != (build / rel).read_bytes():
                    raise ValueError(f"unexpected copied file difference: {rel}")
                preserved += 1
        manifest = {"format": "darksun-view-class-names", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v67"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[POOL_SITE, POOL_SITE + POOL_LEN], [TABLE_SITE, TABLE_SITE + TABLE_LEN]],
                "main_mz_relocations_added": 0},
            "resource": {"sha256": sha256(resource), "unchanged": True},
            "bank5": {"sha256": sha256(bank5), "glyphs": bank5_count,
                "new_characters": {c: by_char[c] for c in NEW_CLASS_CHARACTERS}},
            "scope": {"class_names": "record+0x21..0x23, 8 names (Cleric/Druid/Fighter/Gladiator/"
                    "Preserver/Psionic/Ranger/Thief) translated via a plain DGROUP data patch -- "
                    "no EXE code redirect needed",
                "class_ids_18_20": "left untouched (\" MAGE\"/\"CLERIC\"/\"PSlONlC\", unexplained, not seen in play)",
                "level_exp_dam": "not in this candidate, still pending (see re_88)"},
            "preserved_parent_files": preserved}
        (build / "build-view-class-names-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V68-READ-ME.txt").write_text(
            "v68: VIEW CHARACTER class names translated (Cleric/Druid/Fighter/\n"
            "Gladiator/Preserver/Psionic/Ranger/Thief), including multiclass display\n"
            "(e.g. K'Ratchek's \"Fighter/Druid/Psionic\"). This is a pure data patch --\n"
            "a pointer table and string pool in the main resident data segment -- no\n"
            "EXE code redirect. IDs 18-20 (\" MAGE\"/\"CLERIC\"/\"PSlONlC\") are untouched.\n"
            "Level, EXP, and the DAM: label are NOT in this candidate -- see re_88.\n"
            "Runtime validation NOT performed by this script.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V67_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
