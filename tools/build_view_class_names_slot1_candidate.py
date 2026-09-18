#!/usr/bin/env python3
"""Build v68b: VIEW CHARACTER's single-class name display translated.

`re_90` found that overwriting the class-name string pool/table in place
(v68, now abandoned) doesn't work: unlike every other identity field,
that draw call never runs its string through the NAME-slot decode
pipeline, so raw Base94 escape bytes render as literal garbage instead
of CJK glyphs. The real fix needs a proper tag redirect per call site,
same idea as every other field, just repeated once per class slot that
appears in the (overlay-loaded) draw function's three separate code
paths for 1/2/3 simultaneous classes.

This candidate does *only* the single-class path (`5B7C:2F1F` in the
v67-era build, overlay unit 25 -- file_start `0x6FDD0`, confirmed via
`ovr-map.py`, distinct from the overlay HP:/PSI: live in). It replaces
the self-contained 17-byte span "les bx,[bp+0xA]; mov al,es:[bx+0x21];
cbw; dec ax; shl ax,2; mov bx,ax; push dword [bx+si]" -- which reads
class slot 1 and pushes a far pointer straight from the English string
table -- with a 3-byte `mov ax,<tag>` plus the proven 14-byte DS-relative
redirect (same technique `re_89`/v67 validated for this overlay's
sibling), landing on a new FONT-local `class_slot1_label_entry` that
re-reads the same record field, looks up a *translated* class-name table
instead, and hands back a decoded transport-code pointer in the exact
dx:ax shape the original push would have left.

This intentionally leaves the two-class and three-class code paths
(each of which independently repeats the same "read a class slot, look
it up, push it" logic at different addresses) untouched for now, so
only single-classed party members (e.g. GERAKIS) are affected; anyone
multiclassed (e.g. K'RATCHEK) keeps seeing English "Fighter/Druid/
Psionic" until a follow-up candidate extends the same technique to
those two remaining code paths. Validate this one live before doing
that -- it's the cheapest way to prove the whole redirect shape works
before repeating it four more times.

Only 8 distinct class names exist across the first 17 class IDs (see
`re_89`'s survey): 牧師 (Cleric), 德魯伊 (Druid), 戰士 (Fighter), 角鬥士
(Gladiator), 保育師 (Preserver), 靈能師 (Psionic), 遊俠 (Ranger), 盜賊
(Thief). Six new glyphs (牧/魯/育/俠/盜/賊) land in bank 5, growing it
from 44 to 50 -- the same mapping extension the abandoned v68 already
computed, reused here since it was never the source of that build's bug.
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
    from .build_view_alignment_reposition_candidate import LABELS
    from .cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, rasterizer, build_bank, update_mapping, verify_extracted_gff_chunks,
    )
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, ds_relative_consumer_redirect_bytes
except ImportError:
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from build_view_character_candidate import verify_overlay_relocations
    from build_view_alignment_reposition_candidate import LABELS
    from cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, rasterizer, build_bank, update_mapping, verify_extracted_gff_chunks,
    )
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, ds_relative_consumer_redirect_bytes

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v68b_view_class_names_slot1"
V67_ROOT = ROOT / "scratch_test/cjk_display_staging_v67_view_hp_psi_labels"
PARENT_EXE_HASH = "39a18dd6e6c9c80e9a3076929cece2bdc4453c1b5950471ee2ffba7b9e4d101b"
PARENT_RESOURCE_HASH = "3520b38388cd60cf3f379a41df4707ab899989c344fc51ff21a60610b5a4f589"

OVERLAY_25_FILE_START = 0x6FDD0

CLASS_SLOT1_TAG = 0xFF90
CLASS_SLOT1_SITE = 0x72CEF
CLASS_SLOT1_LEN = 17
CLASS_SLOT1_ORIGINAL = bytes.fromhex("c45e0a268a47219848c1e0028bd866ff30")
CLASS_SLOT1_CONTINUATION_IP = (CLASS_SLOT1_SITE + CLASS_SLOT1_LEN) - OVERLAY_25_FILE_START

NEW_CLASS_CHARACTERS = "牧魯育俠盜賊"


def _tag_redirect(tag: int, continuation_ip: int, span_len: int) -> bytes:
    stub = bytes.fromhex("B8") + tag.to_bytes(2, "little") + ds_relative_consumer_redirect_bytes(continuation_ip)
    if len(stub) > span_len:
        raise ValueError("class name slot redirect does not fit")
    return stub.ljust(span_len, b"\x90")


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v67")
    if image[CLASS_SLOT1_SITE:CLASS_SLOT1_SITE + CLASS_SLOT1_LEN] != CLASS_SLOT1_ORIGINAL:
        raise ValueError("class slot 1 consumer differs")
    verify_overlay_relocations(image, [(CLASS_SLOT1_SITE, CLASS_SLOT1_SITE + CLASS_SLOT1_LEN)])
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    result[CLASS_SLOT1_SITE:CLASS_SLOT1_SITE + CLASS_SLOT1_LEN] = _tag_redirect(
        CLASS_SLOT1_TAG, CLASS_SLOT1_CONTINUATION_IP, CLASS_SLOT1_LEN)
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("class slot 1 patch changed main MZ relocations")
    allowed = set(range(CLASS_SLOT1_SITE, CLASS_SLOT1_SITE + CLASS_SLOT1_LEN))
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
    render = rasterizer(ROOT / "Fonts/Fusion_Pixel_10px.ttf", font_size=10, pixel_width=10, height=10,
                         advance=10, threshold=64, fit_mode="pixel-aligned", add_shadow=True,
                         clamp_shadow_bottom=False)
    bank5_entries = [e for e in candidate["entries"] if e["bank"] == 5]
    payload = build_bank(5, bank5_entries, 10, render)
    return candidate, payload, len(bank5_entries)


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v67")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v67")
    patched = patch_executable(exe)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-class-names-slot1-v68b-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"
        for name in ("C0", "C1", "C2", "C3", "C4"):
            if sha256((game / name).read_bytes()) != sha256((source / "GAME/DARKSUN" / name).read_bytes()):
                raise AssertionError(f"unexpected pre-existing drift in parent {name}")

        mapping, bank5, bank5_count = extend_mapping_and_rebuild_bank5(source / "cjk-mapping-v57.json")
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
        manifest = {"format": "darksun-view-class-names-slot1", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v67"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[CLASS_SLOT1_SITE, CLASS_SLOT1_SITE + CLASS_SLOT1_LEN]],
                "overlay_index": 25,
                "overlay_continuation_ip": CLASS_SLOT1_CONTINUATION_IP,
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "bank5": {"sha256": sha256(bank5), "glyphs": bank5_count,
                "new_characters": {c: by_char[c] for c in NEW_CLASS_CHARACTERS}},
            "scope": {"class_slot1": "record+0x21, single-class draw path (5B7C:2F1F) only -- "
                    "translated via a proper NAME-slot tag redirect this time (see re_90)",
                "class_slot2_slot3": "not in this candidate -- 2-class/3-class draw paths still English",
                "level_exp_dam": "not in this candidate, still pending (see re_88)"},
            "preserved_parent_files": preserved}
        (build / "build-view-class-names-slot1-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V68b-READ-ME.txt").write_text(
            "v68b: VIEW CHARACTER's single-class name display translated (e.g.\n"
            "GERAKIS's \"Gladiator\" -> \"角鬥士\"), via a proper NAME-slot tag\n"
            "redirect at the single-class draw path (overlay 25). The abandoned v68\n"
            "tried overwriting the string table/pool directly and produced garbage --\n"
            "see re_90 for why that doesn't work here.\n"
            "Multiclass characters (e.g. K'RATCHEK) are UNCHANGED in this candidate --\n"
            "the two-class and three-class draw paths each independently repeat the\n"
            "same lookup at different addresses and need their own redirects, planned\n"
            "as a follow-up once this single-class path is confirmed working live.\n"
            "Level, EXP, and the DAM: label are also not in this candidate -- see re_88.\n"
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
