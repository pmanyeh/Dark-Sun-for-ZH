#!/usr/bin/env python3
"""Build isolated v62: Chinese weapon/armor material adjectives.

Translates the "Bone"/"Wooden"/"Stone"/"Obsidian"/"Metal"/"Leather" prefix
that is prepended onto a weapon's already-CJK-decoded base name (e.g. "Bone
Long Sword"). There is a single shared caller that builds this combined
string; both the bottom hover label and the right-click item card read the
same buffer, so one patch covers both.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile

try:
    from .build_ability_ui_candidate import LABELS
    from .build_backpack_ui_candidate import ROOT, sha256
    from .build_fixed_labels_candidate import DEFAULT_OUTPUT as V61_ROOT, LABEL_IDS
    from .build_name_slot_candidate_from_v33 import run
    from .build_view_character_candidate import verify_overlay_relocations
    from .cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache
except ImportError:
    from build_ability_ui_candidate import LABELS
    from build_backpack_ui_candidate import ROOT, sha256
    from build_fixed_labels_candidate import DEFAULT_OUTPUT as V61_ROOT, LABEL_IDS
    from build_name_slot_candidate_from_v33 import run
    from build_view_character_candidate import verify_overlay_relocations
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v62_material_labels"
PARENT_EXE_HASH = "3c56a1a724e1de0e0656a91c96a088cf6bd15b453e0f83a21315bd3d0653b879"
PARENT_RESOURCE_HASH = "fbfd002aa42b43a76dfaed473b8de35dac802a5220d7d48ec9bb162025a2abba"
VIEW_Y_ORIGIN = 43

# Runtime-confirmed via a live DOSBox-X breakpoint on the shared FONT-local
# decode entry point (36AA:5414): opening this exact 32-byte span reads a
# material-index (0..5, already range-checked by the untouched code right
# before it) into DX's low nibble, looks up ES=<resident material-string
# segment>:[material_index*4] (a fixed six-entry far-pointer table, confirmed
# to hold Wooden/Bone/Stone/Obsidian/Metal/Leather), and strcpy's the English
# adjective into the same ss:[bp-0x28] stack buffer that will have the item's
# already-decoded base name appended right after it. Both the bottom hover
# label and the right-click item card read this one combined buffer -- there
# is only one caller to patch.
#
# Two overlay-relocated far-call/segment words (an unrelated "mov ax,0x378"
# segment immediate, and this span's own "lcall 0,0x37e4" far-call segment)
# sit inside this 32-byte region, splitting it into two writable zones with
# nothing safe wide enough for the usual 22-byte self-computing stub on its
# own. The material_label_entry outer-dispatch stub is instead hand-split
# across both zones: zone 1 computes the self-relative continuation IP into
# AX and jumps to zone 2, which pushes (cs, AX) in the same order the
# unsplit stub would have and finishes the jump into the resident
# trampoline. The two relocated words themselves are never written -- since
# this redirect always transfers control away before reaching them, they
# become unreachable dead code, exactly like a plain skip_bytes gap.
MATERIAL_SITE = 0x6E241
# Original bytes, in order: 9 safe / 2 relocated ("mov ax,0x378" segment
# immediate) / 16 safe / 2 relocated ("lcall 0,0x37e4" far-call segment) /
# 3 safe ("add sp,8", already dead code once this redirect is in place).
ZONE_1_BYTES = bytes.fromhex("8bda83e30fc1e302b8")
GAP_1 = bytes.fromhex("7803")
ZONE_2_BYTES = bytes.fromhex("8ec06626ffb70000168d46d8509ae437")
GAP_2 = bytes.fromhex("0000")
TAIL_BYTES = bytes.fromhex("83c408")
MATERIAL_ORIGINAL = ZONE_1_BYTES + GAP_1 + ZONE_2_BYTES + GAP_2 + TAIL_BYTES
ZONE_1_SITE = MATERIAL_SITE
ZONE_1_LEN = len(ZONE_1_BYTES)
ZONE_2_SITE = ZONE_1_SITE + ZONE_1_LEN + len(GAP_1)
ZONE_2_LEN = len(ZONE_2_BYTES)
CONTINUATION_IP = MATERIAL_SITE + len(MATERIAL_ORIGINAL)
MATERIAL_TAG = 0xFFE7


def split_material_redirect() -> tuple[bytes, bytes]:
    """Hand-build the two zone-1/zone-2 halves of the split outer stub."""
    call_addr = ZONE_1_SITE
    call_return = call_addr + 3
    delta = CONTINUATION_IP - call_return
    if not 0 <= delta <= 0xFFFF:
        raise ValueError("split material redirect delta out of range")
    zone1 = bytes.fromhex("E8 00 00 58 05".replace(" ", "")) + struct.pack("<H", delta)
    jump_from = call_addr + len(zone1) + 2
    displacement = ZONE_2_SITE - jump_from
    if not -128 <= displacement <= 127:
        raise ValueError("split material redirect jump does not fit a short jump")
    zone1 += b"\xEB" + struct.pack("<b", displacement)
    if len(zone1) != ZONE_1_LEN:
        raise AssertionError("zone 1 length mismatch")
    zone2 = bytes.fromhex("0E 50".replace(" ", "")) + b"\xB8" + struct.pack("<H", MATERIAL_TAG)
    zone2 += bytes.fromhex("8C DB 80 EF 10 53 68 14 07 CB".replace(" ", ""))
    if len(zone2) > ZONE_2_LEN:
        raise ValueError("split material redirect zone 2 does not fit")
    zone2 = zone2.ljust(ZONE_2_LEN, b"\x90")
    return zone1, zone2


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v61")
    end = MATERIAL_SITE + len(MATERIAL_ORIGINAL)
    if image[MATERIAL_SITE:end] != MATERIAL_ORIGINAL:
        raise ValueError("material consumer differs")
    verify_overlay_relocations(image, [(ZONE_1_SITE, ZONE_1_SITE + ZONE_1_LEN), (ZONE_2_SITE, ZONE_2_SITE + ZONE_2_LEN)])
    relocations = mz_relocation_file_offsets(image)
    zone1, zone2 = split_material_redirect()
    result = bytearray(image)
    result[ZONE_1_SITE:ZONE_1_SITE + ZONE_1_LEN] = zone1
    result[ZONE_2_SITE:ZONE_2_SITE + ZONE_2_LEN] = zone2
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("material patch changed main MZ relocations")
    allowed = set(range(ZONE_1_SITE, ZONE_1_SITE + ZONE_1_LEN)) | set(range(ZONE_2_SITE, ZONE_2_SITE + ZONE_2_LEN))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v61")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v61")
    patched = patch_executable(exe)
    mapping = load_mapping(source / "cjk-mapping-v57.json")
    by_char = {entry["character"]: entry["id"] for entry in mapping["entries"]}
    ability_ids = tuple(by_char[c] for c in "".join(LABELS))
    base_options = dict(backpack_ids=(1303, 100), ability_ids=ability_ids, view_character=True, view_y_origin=VIEW_Y_ORIGIN)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="material-labels-v62-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"
        font_path = work / "font.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        original_font = font_path.read_bytes()
        if original_font[FONT_CORE_PAYLOAD_OFFSET:] != assemble_name_slot_cache(**base_options, label_ids=LABEL_IDS):
            raise ValueError("v61 FONT/core mismatch")
        font = original_font[:FONT_CORE_PAYLOAD_OFFSET] + assemble_name_slot_cache(**base_options, label_ids=LABEL_IDS, materials=True)
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
        manifest = {"format": "darksun-material-labels-candidate", "version": 1,
            "validation": {"runtime_status": "not_run", "material_label_status": "pending"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[ZONE_1_SITE, ZONE_1_SITE + ZONE_1_LEN], [ZONE_2_SITE, ZONE_2_SITE + ZONE_2_LEN]],
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font)},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {
                "materials": {"Wooden": "木製", "Bone": "骨製", "Stone": "石製",
                    "Obsidian": "黑石製 (simplified from 黑曜石製: 曜 has no glyph yet)",
                    "Metal": "金屬製", "Leather": "皮製"},
                "affects": "bottom hover label and right-click item card (shared buffer)",
                "view_character_lower_panel": "unchanged", "ac_psi_labels": "unchanged (already Chinese from v61)"},
            "preserved_parent_files": preserved}
        (build / "build-material-labels-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V62-READ-ME.txt").write_text(
            "v62: Chinese weapon/armor material adjectives (木製/骨製/石製/黑石製/金屬製/皮製).\n"
            "All six reuse glyph IDs already shipped in dialogue text except one simplification (see manifest scope).\n"
            "Affects the bottom hover label and the right-click item card, which share one build buffer.\n"
            "Runtime validation NOT performed. Use build-material-labels-manifest.json; older manifests describe ancestors.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V61_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
