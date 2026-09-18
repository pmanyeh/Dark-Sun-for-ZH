#!/usr/bin/env python3
"""Build v66: alignment moves onto the equipment row; gender rejoins race.

Per the user's new layout reference, alignment (e.g. CHAOTIC GOOD) should
sit on the top row next to the three equipment slots -- the spot v65 gave
to gender -- while gender goes back to sharing race's row exactly as v64
had it (e.g. "MALE HALF-GIANT" on one line). This candidate is therefore
built directly on **v64**, not v65: v64 already has gender+race combined
on row y=86 with no further changes needed there, so v65's gender-only
reposition is simply not applied.

Alignment's real draw site was never v64/v65's assumed call site
(0x8A1DC's target, `5FB0:19A8`) after all -- live tracing this session
found that address IS the alignment draw function; re_86's dead end came
from reading past its own `retf` into the next field's code, which
happens to also check `es:[bx+0x18]==1` for an unrelated reason and was
mistaken for the whole story. `5FB0:19A8` (file offset 0x64BF8) reads
`es:[bx+0x1A]` -- alignment, 1-indexed 1-9 in AD&D's classic 3x3
law/chaos-then-good/evil grid order -- multiplies by 4 into a small
English string table, and calls the same "%C%C%C%s" formatter used by
gender, race, and the AC:/PSI: labels.

That function's trailing argument shape (color escape, template id,
position pair, then the caller's own [bp+6] far pointer) is byte-for-byte
identical to gender's own draw call, right up to -- but not including --
the still-untouched far call itself (its segment word is an overlay
relocation target). So the patch mirrors v65's gender_decoded technique
exactly: one 50-byte tag redirect absorbing the record read, the English
table lookup, and all of the original argument pushes, replaced by a
FONT-local `alignment_decoded` that re-reads record+0x1A itself, looks up
a 9-entry Chinese string table, and pushes fixed (ALIGNMENT_Y,
ALIGNMENT_X) instead of forwarding the original position.

Alignment's Chinese names are always exactly four characters (e.g.
混亂善良), needing four new glyphs (序/善/良/立) beyond the eight already
shipped for race/gender. Following the same established pattern as v64,
this extends the *parent candidate's own* mapping copy, not the root
file; all four new characters land in bank 5 (C5), the same bank v64
already modified, growing it from 40 to 44 glyphs.
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
    from .build_view_identity_candidate import DEFAULT_OUTPUT as V64_ROOT, LABELS
    from .cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, rasterizer, build_bank, update_mapping, verify_extracted_gff_chunks,
    )
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, self_relative_tag_redirect
except ImportError:
    from build_backpack_ui_candidate import ROOT, sha256
    from build_name_slot_candidate_from_v33 import run
    from build_view_character_candidate import verify_overlay_relocations
    from build_view_identity_candidate import DEFAULT_OUTPUT as V64_ROOT, LABELS
    from cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, rasterizer, build_bank, update_mapping, verify_extracted_gff_chunks,
    )
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, self_relative_tag_redirect

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v66_view_alignment_reposition"
PARENT_EXE_HASH = "cf66f622557ca0f12e5e03c128c4e4e0c769217a7339103e4efc3cc94133a551"
PARENT_RESOURCE_HASH = "8a5ffd8a1d348abb3907d9035f1d4b6441228faa64804c8d2f03d4e0b812d297"
# v64's own FONT-100. The shared asm source is edited in place again for
# this candidate (new alignment entries), so the parent font can no
# longer be re-derived by reassembling it -- check its hash instead.
PARENT_FONT_HASH = "626af82d3a90615d390808f8118a67a42ad99c4a620fc26848020b685373c716"

FONT_PATH = ROOT / "Fonts/Fusion_Pixel_10px.ttf"
RASTER_OPTIONS = dict(font_size=10, pixel_width=10, height=10, advance=10, threshold=64,
                       fit_mode="pixel-aligned", add_shadow=True, clamp_shadow_bottom=False)

ALIGNMENT_TAG = 0xFFCB
ALIGNMENT_Y, ALIGNMENT_X = 44, 149

ALIGNMENT_SITE = 0x64BFB
ALIGNMENT_ZONE_LEN = 50
ALIGNMENT_ORIGINAL = bytes.fromhex(
    "c45e0a268a471a98c1e0028bd866ffb7060fff3670326a14ff366e326668ff00fe006a001e68110e"
    "ff7610ff760e66ff7606"
)

NEW_ALIGNMENT_CHARACTERS = "序善良立"


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v64")
    if image[ALIGNMENT_SITE:ALIGNMENT_SITE + len(ALIGNMENT_ORIGINAL)] != ALIGNMENT_ORIGINAL:
        raise ValueError("alignment consumer differs")
    verify_overlay_relocations(image, [(ALIGNMENT_SITE, ALIGNMENT_SITE + ALIGNMENT_ZONE_LEN)])
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    result[ALIGNMENT_SITE:ALIGNMENT_SITE + ALIGNMENT_ZONE_LEN] = self_relative_tag_redirect(
        ALIGNMENT_TAG, ALIGNMENT_ZONE_LEN)
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("alignment patch changed main MZ relocations")
    allowed = set(range(ALIGNMENT_SITE, ALIGNMENT_SITE + ALIGNMENT_ZONE_LEN))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def extend_mapping_and_rebuild_bank5(parent_mapping_path: Path) -> tuple[dict, bytes, int]:
    """Return (mapping_document, new_bank5_bytes, bank5_glyph_count)."""
    mapping = load_mapping(parent_mapping_path)
    candidate = update_mapping(mapping, Counter(NEW_ALIGNMENT_CHARACTERS), [])
    by_char = {e["character"]: e for e in candidate["entries"]}
    for character in NEW_ALIGNMENT_CHARACTERS:
        if by_char[character]["bank"] != 5:
            raise ValueError(f"expected {character!r} to land in bank 5, got {by_char[character]['bank']}")
    render = rasterizer(FONT_PATH, **RASTER_OPTIONS)
    bank5_entries = [e for e in candidate["entries"] if e["bank"] == 5]
    payload = build_bank(5, bank5_entries, RASTER_OPTIONS["height"], render)
    return candidate, payload, len(bank5_entries)


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v64")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v64")
    patched = patch_executable(exe)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-alignment-reposition-v66-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"

        mapping, bank5, bank5_count = extend_mapping_and_rebuild_bank5(source / "cjk-mapping-v57.json")
        for name in ("C0", "C1", "C2", "C3", "C4"):
            if sha256((game / name).read_bytes()) != sha256((source / "GAME/DARKSUN" / name).read_bytes()):
                raise AssertionError(f"unexpected pre-existing drift in parent {name}")

        by_char = {e["character"]: e["id"] for e in mapping["entries"]}
        ability_ids = tuple(by_char[c] for c in "".join(LABELS))
        label_ids = (by_char["防"], by_char["禦"], by_char["靈"], by_char["能"])
        base_options = dict(backpack_ids=(1303, 100), ability_ids=ability_ids,
            view_character=True, view_y_origin=63, identity=True,
            alignment_position=(ALIGNMENT_Y, ALIGNMENT_X))

        font_path = work / "font.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        original_font = font_path.read_bytes()
        if sha256(original_font) != PARENT_FONT_HASH:
            raise ValueError("v64 FONT does not match the reviewed pre-alignment font")
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
        manifest = {"format": "darksun-view-alignment-reposition", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v64"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[ALIGNMENT_SITE, ALIGNMENT_SITE + ALIGNMENT_ZONE_LEN]],
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "bank5": {"sha256": sha256(bank5), "glyphs": bank5_count,
                "new_characters": {c: by_char[c] for c in NEW_ALIGNMENT_CHARACTERS}},
            "scope": {"alignment": f"record+0x1A, nine-entry table, moved to (x={ALIGNMENT_X}, y={ALIGNMENT_Y}) "
                    "next to the equipment slots (v65's real draw-site dead end resolved: 5FB0:19A8 IS alignment)",
                "gender": "record+0x19, unchanged from v64 -- short redirect, natural (x=149, y=86) sharing race's row",
                "race": "record+0x18, unchanged from v64 -- still right after gender on the same row",
                "class_level_exp_hp_psi": "not in this candidate, still pending"},
            "preserved_parent_files": preserved}
        (build / "build-view-alignment-reposition-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V66-READ-ME.txt").write_text(
            "v66: alignment (e.g. CHAOTIC GOOD -> 混亂善良) moved onto the\n"
            "equipment row and translated; gender moved back down to share\n"
            "race's row exactly as v64 had it (e.g. MALE HALF-GIANT).\n"
            "Alignment's real draw function turned out to be 5FB0:19A8 all\n"
            "along -- the same address v65 investigated and dismissed as\n"
            "unrelated logic, which was actually the alignment field itself\n"
            "(the 'unrelated' human-race/level-2 popup check that dead-ended\n"
            "that investigation is the NEXT field's code, past this\n"
            "function's own retf). Runtime validation NOT performed by this\n"
            "script -- see the checkpoint doc for live verification.\n",
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
