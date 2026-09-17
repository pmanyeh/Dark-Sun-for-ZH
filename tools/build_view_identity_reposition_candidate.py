#!/usr/bin/env python3
"""Build v65: move gender up onto the equipment row; race stays in place.

Per the user's layout reference, gender should sit on the top row next to
the three equipment slots, while race stays where the combined "gender
race" line used to be (now just race, starting where gender used to
start). Alignment is intentionally left untouched in this candidate: the
call site earlier documentation (and this session's own earlier guess)
attributed to alignment turned out, on live re-verification, to route into
unrelated logic (a human-race/level-2 special-condition check that shares
the same generic overlay "library" as several other UI rows, including
this project's own already-shipped AC: label). Where alignment is actually
drawn is still unknown; moving or combining it is deferred.

Two changes to v64's gender redirect:

1. Zone A (0x64B68, 14 bytes) still writes a fixed width into [bp-2], but
   now writes 0 instead of ~24px, since race no longer needs to be offset
   past a gender string that is no longer drawn on the same line.
2. Zone C (0x64B83) grows from v64's 22 bytes to 46 bytes: it now also
   absorbs the original code's remaining argument pushes (color escape,
   template id, and the position pair that used to come from DI/SI) up to
   -- but not including -- the still-untouched "call 339E:016D" draw
   itself. The FONT-local gender_decoded pushes a fixed (GENDER_X,
   GENDER_Y) pair instead of forwarding DI/SI, and re-pushes everything
   else exactly as the original code would have.

The race redirect (0x64BB9) and the FONT core's race table are unchanged
from v64; no new characters or glyph banks are needed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile

try:
    from .build_backpack_ui_candidate import ROOT, sha256
    from .build_name_slot_candidate_from_v33 import run
    from .build_view_character_candidate import verify_overlay_relocations
    from .build_view_identity_candidate import DEFAULT_OUTPUT as V64_ROOT, LABELS
    from .build_view_identity_candidate import gender_zone_a as v64_gender_zone_a
    from .cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, self_relative_tag_redirect
except ImportError:
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from build_view_character_candidate import verify_overlay_relocations
    from build_view_identity_candidate import DEFAULT_OUTPUT as V64_ROOT, LABELS
    from build_view_identity_candidate import gender_zone_a as v64_gender_zone_a
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, self_relative_tag_redirect

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v65_view_gender_reposition"
PARENT_EXE_HASH = "cf66f622557ca0f12e5e03c128c4e4e0c769217a7339103e4efc3cc94133a551"
PARENT_RESOURCE_HASH = "8a5ffd8a1d348abb3907d9035f1d4b6441228faa64804c8d2f03d4e0b812d297"
# v64's own FONT-100. The shared asm source is edited in place again for
# this candidate, so the parent font can no longer be re-derived by
# reassembling it -- check its hash instead.
PARENT_FONT_HASH = "626af82d3a90615d390808f8118a67a42ad99c4a620fc26848020b685373c716"

GENDER_TAG = 0xFFCD
GENDER_Y, GENDER_X = 44, 149

GENDER_ZONE_A_SITE = 0x64B68
GENDER_ZONE_A_LEN = 14
GENDER_GAP_LEN = 13  # untouched dead code; contains the 0x64B79 overlay relocation
GENDER_ZONE_C_SITE = GENDER_ZONE_A_SITE + GENDER_ZONE_A_LEN + GENDER_GAP_LEN  # 0x64B83
GENDER_ZONE_C_LEN = 46

V64_GENDER_ZONE_A = v64_gender_zone_a()
assert len(V64_GENDER_ZONE_A) == GENDER_ZONE_A_LEN
V64_GENDER_ZONE_C_TAIL_ORIGINAL = bytes.fromhex(
    "6a14ff366e326668ff00fe006a001e68110e575666ff7606"
)  # the 24 untouched bytes right after v64's 22-byte redirect


def new_gender_zone_a() -> bytes:
    jump_from = GENDER_ZONE_A_SITE + 5 + 2
    displacement = (GENDER_ZONE_A_SITE + GENDER_ZONE_A_LEN + GENDER_GAP_LEN) - jump_from
    if not -128 <= displacement <= 127:
        raise ValueError("gender zone A jump does not fit a short jump")
    zone = bytes.fromhex("C746FE") + struct.pack("<h", 0) + b"\xEB" + struct.pack("<b", displacement)
    return zone.ljust(GENDER_ZONE_A_LEN, b"\x90")


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v64")
    expected_zone_a = V64_GENDER_ZONE_A
    expected_zone_c = self_relative_tag_redirect(GENDER_TAG, 22) + V64_GENDER_ZONE_C_TAIL_ORIGINAL
    if image[GENDER_ZONE_A_SITE:GENDER_ZONE_A_SITE + GENDER_ZONE_A_LEN] != expected_zone_a:
        raise ValueError("v64 gender zone A differs")
    if image[GENDER_ZONE_C_SITE:GENDER_ZONE_C_SITE + GENDER_ZONE_C_LEN] != expected_zone_c:
        raise ValueError("v64 gender zone C differs")
    verify_overlay_relocations(image, [
        (GENDER_ZONE_A_SITE, GENDER_ZONE_A_SITE + GENDER_ZONE_A_LEN),
        (GENDER_ZONE_C_SITE, GENDER_ZONE_C_SITE + GENDER_ZONE_C_LEN),
    ])
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    result[GENDER_ZONE_A_SITE:GENDER_ZONE_A_SITE + GENDER_ZONE_A_LEN] = new_gender_zone_a()
    result[GENDER_ZONE_C_SITE:GENDER_ZONE_C_SITE + GENDER_ZONE_C_LEN] = self_relative_tag_redirect(GENDER_TAG, GENDER_ZONE_C_LEN)
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("gender reposition patch changed main MZ relocations")
    allowed = (set(range(GENDER_ZONE_A_SITE, GENDER_ZONE_A_SITE + GENDER_ZONE_A_LEN))
               | set(range(GENDER_ZONE_C_SITE, GENDER_ZONE_C_SITE + GENDER_ZONE_C_LEN)))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v64")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v64")
    patched = patch_executable(exe)
    mapping = load_mapping(source / "cjk-mapping-v57.json")
    by_char = {e["character"]: e["id"] for e in mapping["entries"]}
    ability_ids = tuple(by_char[c] for c in "".join(LABELS))
    label_ids = (by_char["防"], by_char["禦"], by_char["靈"], by_char["能"])
    base_options = dict(backpack_ids=(1303, 100), ability_ids=ability_ids,
        view_character=True, view_y_origin=63, identity=True, gender_position=(GENDER_Y, GENDER_X))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-identity-reposition-v65-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"

        font_path = work / "font.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        original_font = font_path.read_bytes()
        if sha256(original_font) != PARENT_FONT_HASH:
            raise ValueError("v64 FONT does not match the reviewed pre-reposition font")
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
        manifest = {"format": "darksun-view-identity-reposition", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v64"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[GENDER_ZONE_A_SITE, GENDER_ZONE_A_SITE + GENDER_ZONE_A_LEN],
                                  [GENDER_ZONE_C_SITE, GENDER_ZONE_C_SITE + GENDER_ZONE_C_LEN]],
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids,
                "gender_position": {"x": GENDER_X, "y": GENDER_Y}},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"gender": f"moved to (x={GENDER_X}, y={GENDER_Y}), next to the equipment slots",
                "race": "unchanged position (x=149, same row gender used to share), no longer offset by gender's width",
                "alignment": "still not relocated -- true draw site remains unknown",
                "class_level_exp_hp_psi": "not in this candidate, still pending"},
            "preserved_parent_files": preserved}
        (build / "build-view-identity-reposition-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V65-READ-ME.txt").write_text(
            "v65: gender (男性/女性) moved up next to the equipment slots;\n"
            "race now starts where the combined gender+race text used to start.\n"
            "Alignment (CHAOTIC GOOD etc.) is untouched -- its real draw site is\n"
            "still unknown; the call site earlier assumed to be alignment turned\n"
            "out, on live re-verification, to be unrelated logic. Runtime\n"
            "validation NOT performed.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V64_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
