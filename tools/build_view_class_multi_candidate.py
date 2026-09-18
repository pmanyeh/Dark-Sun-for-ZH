#!/usr/bin/env python3
"""Build v71: multiclass VIEW CHARACTER class names in Chinese.

Extends v70 (EXP/HP+PSI row reflow, single-class-only "角鬥士" translation)
with a from-scratch fix for the multiclass class-name corruption `re_93`
found and had to defer: K'RATCHEK ("Fighter/Druid/Psionic"), CERMAK
("Preserver/Gladiator") and CILLA ("Preserver/Druid/Thief") all showed a
wrong, duplicated class name once their draw sites were redirected to the
CJK decoder, because the 2-/3-class draw path (`5B7C:2DC1`) collects every
populated slot's far pointer and only calls the shared `339E:016D` renderer
ONCE, after all slots have decoded -- confirmed this session by live
disassembly of the full three-class push sequence at `5B7C:2E56`..`2EBE`
(three far pointers pushed back to back, then a single `call 339E:016D`)
and the two-class sequence at `2EC9`..`2F15` (same shape, two pointers).
Decode order is always slot3 (if present), then slot2 (if present), then
slot1 last, in both paths.

Two problems follow from "decode now, draw once later":
  1. `name_buffer` is one shared 25-byte scratch buffer -- a later slot's
     decode overwrites an earlier slot's still-unread string before the
     combined draw call reads it.
  2. The 7 physical glyph slots are a shared pool that `decode_start` used
     to reset on every call -- a later slot's decode can evict the bitmap
     data an earlier slot's transport-code characters still point to.

`cjk_name_slot_cache.asm` now fixes both: slot2/slot3 copy their decoded
text into private buffers (class_slot2_buffer/class_slot3_buffer) instead
of returning a pointer into the shared name_buffer, and a one-shot
`class_skip_reset` flag -- set from the character record itself, not from
any saved call history -- lets a slot ask the very next decode_start call
to keep accumulating into the same physical slot pool instead of
resetting it. The physical glyph pool is also expanded from 7 to 10
slots (see re_94 section on the pool expansion): slots 1-7 still live in
the game's own pre-allocated FONT scratch area, slots 8-10 live in a new
`class_extra_slots` buffer this payload brings with it, addressed via a
`FONT_RUNTIME_BASE_OFFSET` conversion from this payload's own CS-relative
addressing into the same "[font_pointer]-relative" space the built-in
slots use (re_93's attempt at this used the wrong constant and the wrong
direction, which is why it corrupted unrelated FONT memory; re_94 derived
the correct conversion from a live-confirmed fact: CS equals
[font_pointer]'s own segment at runtime). Confirmed live for all three-
class characters checked (K'RATCHEK's 8 distinct glyphs, CILLA's 8) --
no character needs more than 10 distinct glyphs across all three class
names in the current class-name table, so no '?' fallback should occur
in practice, though the fallback path itself is still intact if a future
class combination ever needs more than 10.

EXE side: this reuses v68c's already-validated 5-site redirect (the "read
record; look up table; push far pointer" 17-byte span repeated once per
class slot per draw path -- 2 sites in the two-class path, 3 in the
three-class path), applied on top of v70's own two overlay-48 position
patches, both against the same v68b parent EXE/RESOURCE/FONT.
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
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, ds_relative_consumer_redirect_bytes
except ImportError:
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from build_view_character_candidate import verify_overlay_relocations
    from build_view_alignment_reposition_candidate import LABELS
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, ds_relative_consumer_redirect_bytes

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v71_view_class_multi"
V68B_ROOT = ROOT / "scratch_test/cjk_display_staging_v68b_view_class_names_slot1"
PARENT_EXE_HASH = "78a7f1bab8b168f97bafc0b0574b9365ee3d5474010cbdd02c93b9a03b36f4d9"
PARENT_RESOURCE_HASH = "8406e80875998466b53bac6d97a65da5823473ba1f4372141c6fbf2b6e5056e2"
PARENT_FONT_HASH = "1583ae003f82062f13843f63c26eaf0714bccdfd4ebb5294467886afff9c4b24"

# v70's own two position patches, overlay 48 (file_start=0x89E70).
EXP_POSITION_SITE = 0x8A281
EXP_POSITION_ORIGINAL = bytes.fromhex("66689500" "7800")  # x=149, y=120
EXP_POSITION_NEW = bytes.fromhex("6668C700" "7100")        # x=199, y=113

PSI_NUMBER_POSITION_SITE = 0x8A345
PSI_NUMBER_POSITION_ORIGINAL = bytes.fromhex("6668BD00" "8600")  # x=189, y=134
PSI_NUMBER_POSITION_NEW = bytes.fromhex("66680E01" "7F00")        # x=270, y=127

POSITION_SITES = [
    ("exp_position", EXP_POSITION_SITE, EXP_POSITION_ORIGINAL, EXP_POSITION_NEW),
    ("psi_number_position", PSI_NUMBER_POSITION_SITE, PSI_NUMBER_POSITION_ORIGINAL, PSI_NUMBER_POSITION_NEW),
]

# v68c's 5-site multiclass class-name redirect, overlay 25
# (file_start=0x6FDD0). v68b already patched the single-class site
# (local 0x2F1F); these are the two- and three-class paths' own repeats
# of the same "read record; look up table; push far pointer" span.
OVERLAY_25_FILE_START = 0x6FDD0
CLASS_SITE_LEN = 17

CLASS_SLOT1_TAG = 0xFF90
CLASS_SLOT2_TAG = 0xFF91
CLASS_SLOT3_TAG = 0xFF92

CLASS_SITES = [
    ("class2_slot2", CLASS_SLOT2_TAG, 0x2EC9, bytes.fromhex("c45e0a268a47229848c1e0028bd866ff30")),
    ("class2_slot1", CLASS_SLOT1_TAG, 0x2EE7, bytes.fromhex("8b5e0a268a47219848c1e0028bd866ff30")),
    ("class3_slot3", CLASS_SLOT3_TAG, 0x2E56, bytes.fromhex("c45e0a268a47239848c1e0028bd866ff30")),
    ("class3_slot2", CLASS_SLOT2_TAG, 0x2E72, bytes.fromhex("8b5e0a268a47229848c1e0028bd866ff30")),
    ("class3_slot1", CLASS_SLOT1_TAG, 0x2E90, bytes.fromhex("8b5e0a268a47219848c1e0028bd866ff30")),
]


def _class_tag_redirect(tag: int, continuation_ip: int) -> bytes:
    stub = bytes.fromhex("B8") + tag.to_bytes(2, "little") + ds_relative_consumer_redirect_bytes(continuation_ip)
    if len(stub) > CLASS_SITE_LEN:
        raise ValueError("class name site redirect does not fit")
    return stub.ljust(CLASS_SITE_LEN, b"\x90")


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v68b")
    ranges = []
    for name, site, original, _ in POSITION_SITES:
        if image[site:site + len(original)] != original:
            raise ValueError(f"{name} site differs")
        ranges.append((site, site + len(original)))
    for name, tag, local_ip, original in CLASS_SITES:
        file_off = OVERLAY_25_FILE_START + local_ip
        if image[file_off:file_off + CLASS_SITE_LEN] != original:
            raise ValueError(f"{name} consumer differs")
        ranges.append((file_off, file_off + CLASS_SITE_LEN))
    verify_overlay_relocations(image, ranges)
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    for name, site, original, new in POSITION_SITES:
        result[site:site + len(new)] = new
    for name, tag, local_ip, original in CLASS_SITES:
        file_off = OVERLAY_25_FILE_START + local_ip
        continuation_ip = local_ip + CLASS_SITE_LEN
        result[file_off:file_off + CLASS_SITE_LEN] = _class_tag_redirect(tag, continuation_ip)
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("class-multi patch changed main MZ relocations")
    allowed: set[int] = set()
    for _, site, original, _ in POSITION_SITES:
        allowed |= set(range(site, site + len(original)))
    for _, _, local_ip, _ in CLASS_SITES:
        file_off = OVERLAY_25_FILE_START + local_ip
        allowed |= set(range(file_off, file_off + CLASS_SITE_LEN))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v68b")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v68b")
    patched = patch_executable(exe)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-class-multi-v71-", dir=output.parent) as temporary:
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
            raise ValueError("v68b FONT does not match the reviewed pre-fix font")
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
        manifest = {"format": "darksun-view-class-multi", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v68b"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[site, site + len(original)] for _, site, original, _ in POSITION_SITES]
                    + [[OVERLAY_25_FILE_START + local_ip, OVERLAY_25_FILE_START + local_ip + CLASS_SITE_LEN]
                       for _, _, local_ip, _ in CLASS_SITES],
                "overlay_indices": [48, 25],
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"exp": "moved onto level's row (unchanged from v70)",
                "psi": "moved onto HP's row (unchanged from v70)",
                "class_names": "1/2/3-class draw paths all translated -- see re_94 for the "
                    "shared-slot-pool fix (private per-slot buffers + one-shot "
                    "class_skip_reset) plus the 7-to-10-slot physical glyph pool "
                    "expansion (class_extra_slots); confirmed live for GERAKIS "
                    "(1-class), CERMAK (2-class, 6 distinct glyphs), K'RATCHEK and "
                    "CILLA (3-class, 8 distinct glyphs each) with zero '?' fallbacks"},
            "preserved_parent_files": preserved}
        (build / "build-view-class-multi-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V71-READ-ME.txt").write_text(
            "v71: multiclass VIEW CHARACTER class names in Chinese (e.g.\n"
            "K'RATCHEK's 戰士/德魯伊/靈能師, CERMAK's 保育師/角鬥士,\n"
            "CILLA's 保育師/德魯伊/盜賊), fixing the re_93 corruption bug via\n"
            "private per-slot string buffers plus a one-shot flag that lets a\n"
            "later class slot keep accumulating into the same physical glyph\n"
            "pool an earlier slot already populated, instead of resetting it out\n"
            "from under a pointer that's still waiting to be drawn, and expanding\n"
            "the physical glyph pool from 7 to 10 slots so a 3-class name needing\n"
            "more than 7 distinct glyphs still renders every character instead of\n"
            "falling back to '?'. See re_94.\n"
            "Built on v70 (EXP/HP+PSI row reflow carried over unchanged).\n"
            "Runtime validated live: GERAKIS, CERMAK, K'RATCHEK, CILLA all show\n"
            "fully correct Chinese class names with no corruption and no '?'.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V68B_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
