#!/usr/bin/env python3
"""Build isolated v61: Chinese "AC:" and "PSI:" inventory-panel labels.

This is a fixed-string candidate, not a change to any per-character data.
Weapon/race damage rows, VIEW CHARACTER's lower identity panel, and the
BACKPACK/ability-label work already shipped in v56/v57 are untouched.
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
    from .build_name_slot_candidate_from_v33 import run
    from .build_view_character_candidate import verify_overlay_relocations
    from .build_view_hover_candidate import DEFAULT_OUTPUT as V60_ROOT
    from .cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import (
        FONT_CORE_PAYLOAD_OFFSET,
        assemble_name_slot_cache,
        self_relative_tag_redirect,
    )
except ImportError:
    from build_ability_ui_candidate import LABELS
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from build_view_character_candidate import verify_overlay_relocations
    from build_view_hover_candidate import DEFAULT_OUTPUT as V60_ROOT
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, load_mapping, verify_extracted_gff_chunks
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import (
        FONT_CORE_PAYLOAD_OFFSET,
        assemble_name_slot_cache,
        self_relative_tag_redirect,
    )

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v61_fixed_labels"
PARENT_EXE_HASH = "9ee93d9180a0a3cd9a53a7bf146d904c48695f69c1f6b06b733a453eff8ce9ba"
PARENT_RESOURCE_HASH = "e90624c5a677f8de3191ea9d68a493d19e7654c2a2bd5127510de237a9b156ef"
VIEW_Y_ORIGIN = 43
# 防(794)/禦(560) and 靈(822)/能(629): all four already shipped, real-machine
# proven glyphs in the ETen dialogue banks (occurrences 6, 1, 48, 59 in the
# root catalog) -- this candidate reuses their existing IDs, it does not
# rasterize anything new.
LABEL_IDS = (794, 560, 822, 629)

# The inventory info panel already sprintf's "AC: %2d" into a stack buffer
# before drawing it (lcall 0xa8:2 just before this span). "AC" and "防禦"
# are both exactly two bytes wide, so the redirect only overwrites the first
# two buffer bytes; ':', ' ' and the sprintf'd digits are left untouched and
# the original draw call right after this span is never modified.
AC_SITE = 0x64D8A
AC_ORIGINAL = bytes.fromhex(
    "168d46b050ff3670326a14ff366e326668ff00fe006a001e68110eff760eff760c66ff7606"
)

# "%C%C%CPSI:" is drawn directly (no sprintf); "%C%C%C" is a fixed
# draw-color escape kept as a literal prefix, and "PSI:" (4 bytes) is
# replaced by the 3-byte decoded "靈能:". The replaced span starts one push
# earlier than the string pointer itself (to reach the shared stub's
# 22-byte minimum) and stops before the draw call, whose far-call segment
# word (0x150) is an overlay relocation target that must never be patched.
PSI_SITE = 0x6F60E
PSI_ORIGINAL = bytes.fromhex("6668ff00fe006a001e684c1a6668ec00450066ff36a411")

AC_TAG = 0xFFE9
PSI_TAG = 0xFFEA


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v60")
    sites = ((AC_SITE, AC_ORIGINAL, AC_TAG), (PSI_SITE, PSI_ORIGINAL, PSI_TAG))
    for offset, original, _ in sites:
        if image[offset:offset + len(original)] != original:
            raise ValueError(f"fixed-label consumer differs at 0x{offset:X}")
    verify_overlay_relocations(image, [(o, o + len(b)) for o, b, _ in sites])
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    for offset, original, tag in sites:
        redirect = self_relative_tag_redirect(tag, len(original))
        result[offset:offset + len(redirect)] = redirect
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("fixed-label patch changed main MZ relocations")
    allowed = {i for offset, original, _ in sites for i in range(offset, offset + len(original))}
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v60")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v60")
    patched = patch_executable(exe)
    mapping = load_mapping(source / "cjk-mapping-v57.json")
    by_char = {entry["character"]: entry["id"] for entry in mapping["entries"]}
    ability_ids = tuple(by_char[c] for c in "".join(LABELS))
    base_options = dict(backpack_ids=(1303, 100), ability_ids=ability_ids, view_character=True, view_y_origin=VIEW_Y_ORIGIN)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fixed-labels-v61-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"
        font_path = work / "font.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        original_font = font_path.read_bytes()
        if original_font[FONT_CORE_PAYLOAD_OFFSET:] != assemble_name_slot_cache(**base_options):
            raise ValueError("v60 FONT/core mismatch")
        font = original_font[:FONT_CORE_PAYLOAD_OFFSET] + assemble_name_slot_cache(**base_options, label_ids=LABEL_IDS)
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
        manifest = {"format": "darksun-fixed-labels-candidate", "version": 1,
            "validation": {"runtime_status": "not_run", "ac_label_status": "pending", "psi_label_status": "pending"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[AC_SITE, AC_SITE + len(AC_ORIGINAL)], [PSI_SITE, PSI_SITE + len(PSI_ORIGINAL)]],
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": LABEL_IDS},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"ac_label": "防禦: %2d (in-place, sprintf digits untouched)",
                "psi_label": "%C%C%C靈能: (color escape kept literal)",
                "bone_material": "not in this candidate", "view_character_lower_panel": "unchanged",
                "weapon_race_damage_rows": "unchanged"},
            "preserved_parent_files": preserved}
        (build / "build-fixed-labels-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V61-READ-ME.txt").write_text(
            "v61: Chinese AC:/PSI: inventory-panel labels (防禦/靈能).\n"
            "Both reuse glyph IDs already shipped and proven in dialogue text; no new glyphs were rasterized.\n"
            "Bone/material text, VIEW CHARACTER's lower identity panel and weapon/race damage rows are unchanged.\n"
            "Runtime validation NOT performed. Use build-fixed-labels-manifest.json; older manifests describe ancestors.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V60_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
