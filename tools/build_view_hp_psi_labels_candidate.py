#!/usr/bin/env python3
"""Build v67: VIEW CHARACTER's own "HP:" and "PSI:" labels translated.

These are NOT the same literals `re_83`'s v61 already translated for the
item info panel (`ac_label_entry`/`psi_label_entry`, file offsets 0x497C0
and 0x4A3AC) -- VIEW CHARACTER draws its own separate copies at file
offsets 0x8A2A0 ("%C%C%CHP:\\0") and 0x8A316 ("%C%C%CPSI:\\0"). "AC:"
needed no separate patch here because the item panel's copy is built via
`sprintf("AC: %2d", ...)` from one shared format string, so translating
it once (v61) already covers every screen that draws AC. HP:/PSI: are not
sprintf'd -- each screen embeds its own literal -- so VIEW CHARACTER's
copies need their own redirect, named `view_hp_*`/`view_psi_*` in the
shared asm source to avoid colliding with v61's existing
`psi_label_entry` (a different call site with a different argument
shape).

The instructions that push these string addresses live inside overlay
unit 48 (`file_start=0x89E70`, confirmed via `vendor/opends/tools/ovr-map`
-- the same overlay `build_view_hover_candidate.py`'s already-accepted
v60 patches, and the sibling `dsun-hires-text-poc` experiment independently
identified too). Live-tracing this overlay's *runtime* segment number
across separate redraws showed it is not stable session to session (the
Borland overlay manager can load it into a different segment each time),
which briefly looked like a blocker -- but v60's own hover patch already
proves the fix: `ds_relative_consumer_redirect_bytes`'s "push cs; push
<overlay-local IP>; ...; retf" trampoline captures whatever segment is
*currently* live via `push cs` and only needs a *local* (overlay-relative)
continuation offset, which is a fixed property of the overlay's own file
content and does not depend on which segment it happens to be loaded into.

Each redirect only needs to be 14 bytes (`ds_relative_consumer_redirect_
bytes`) plus a 3-byte `mov ax, <outer tag>` prefix so the shared FONT
dispatcher (`cjk_name_cache_start`) routes to the right entry point -- 17
bytes, fitting inside an 18-byte replaceable span with one NOP byte to
spare. The span is deliberately *narrower* than the full argument run:
it starts right after "push word ptr ds:[0x3270]; push 0x14; push word
ptr ds:[0x326E]" (left completely untouched, since none of that needs to
change) and stops right before the far call itself, whose own segment
word -- like the "0x326E" operand a few bytes earlier and the "0x0430"
ES segment select after it -- is a real overlay-relocation fixup that
must never be overwritten (confirmed empirically: `verify_overlay_
relocations` rejects any span touching those words). The FONT-local
`view_hp_decoded`/`view_psi_decoded` re-push the remaining argument shape
themselves (color dword, zero, the new string pointer, and the position
dword) before returning to the overlay's own untouched continuation.

"HP:" becomes "生命:" (生507/命139, both already-shipped glyphs); "PSI:"
becomes "靈能:" (822/629), matching v61's already-approved item-panel
translation for consistency. No new glyphs, no font bank changes.
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

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v67_view_hp_psi_labels"
# v66's first build had a gender/race stack-corruption bug (see re_87 sec. 4);
# v66b is the corrected, user-validated build this candidate is based on.
V66B_ROOT = ROOT / "scratch_test/cjk_display_staging_v66b_view_alignment_reposition"
PARENT_EXE_HASH = "dc4e44ce9019b1bba4ecb0c192ba44302ebd4fadeb7366f982ee5a3e6e57d32d"
PARENT_RESOURCE_HASH = "2122791e2494fa2f96b128a0ddf9dfd175e752e710bbf6874d8261b3dedefc0a"
PARENT_FONT_HASH = "9fef2ca8d319aa9565ce2dd1270d606be72608b23897cb596781797b290f5827"

OVERLAY_48_FILE_START = 0x89E70

VIEW_HP_TAG = 0xFFC9
VIEW_PSI_TAG = 0xFFCA

# Both spans start right after the untouched "push word ptr ds:[0x3270];
# push 0x14; push word ptr ds:[0x326E]" and stop right before the far call
# (and its overlay-relocated segment word), covering exactly: push dword
# 0x00FE00FF; push 0; push ds; push <label offset>; push dword <Y,X>.
VIEW_HP_SITE = 0x8A2AA
VIEW_PSI_SITE = 0x8A320
LABEL_ZONE_LEN = 18
VIEW_HP_ORIGINAL = bytes.fromhex("6668ff00fe006a001e686333666895007f00")
VIEW_PSI_ORIGINAL = bytes.fromhex("6668ff00fe006a001e686d33666895008600")
VIEW_HP_CONTINUATION_IP = (VIEW_HP_SITE + LABEL_ZONE_LEN) - OVERLAY_48_FILE_START
VIEW_PSI_CONTINUATION_IP = (VIEW_PSI_SITE + LABEL_ZONE_LEN) - OVERLAY_48_FILE_START


def _tag_redirect(tag: int, continuation_ip: int) -> bytes:
    stub = bytes.fromhex("B8") + tag.to_bytes(2, "little") + ds_relative_consumer_redirect_bytes(continuation_ip)
    if len(stub) > LABEL_ZONE_LEN:
        raise ValueError("HP/PSI label redirect does not fit")
    return stub.ljust(LABEL_ZONE_LEN, b"\x90")


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v66b")
    if image[VIEW_HP_SITE:VIEW_HP_SITE + LABEL_ZONE_LEN] != VIEW_HP_ORIGINAL:
        raise ValueError("view HP: label consumer differs")
    if image[VIEW_PSI_SITE:VIEW_PSI_SITE + LABEL_ZONE_LEN] != VIEW_PSI_ORIGINAL:
        raise ValueError("view PSI: label consumer differs")
    verify_overlay_relocations(image, [
        (VIEW_HP_SITE, VIEW_HP_SITE + LABEL_ZONE_LEN),
        (VIEW_PSI_SITE, VIEW_PSI_SITE + LABEL_ZONE_LEN),
    ])
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    result[VIEW_HP_SITE:VIEW_HP_SITE + LABEL_ZONE_LEN] = _tag_redirect(VIEW_HP_TAG, VIEW_HP_CONTINUATION_IP)
    result[VIEW_PSI_SITE:VIEW_PSI_SITE + LABEL_ZONE_LEN] = _tag_redirect(VIEW_PSI_TAG, VIEW_PSI_CONTINUATION_IP)
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("HP/PSI label patch changed main MZ relocations")
    allowed = (set(range(VIEW_HP_SITE, VIEW_HP_SITE + LABEL_ZONE_LEN))
               | set(range(VIEW_PSI_SITE, VIEW_PSI_SITE + LABEL_ZONE_LEN)))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v66b")
    game = source / "GAME/DARKSUN"
    exe, resource = (game / "DSUN.EXE").read_bytes(), (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v66b")
    patched = patch_executable(exe)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-hp-psi-labels-v67-", dir=output.parent) as temporary:
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
            alignment_position=(44, 149))

        font_path = work / "font.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        original_font = font_path.read_bytes()
        if sha256(original_font) != PARENT_FONT_HASH:
            raise ValueError("v66b FONT does not match the reviewed pre-labels font")
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
        manifest = {"format": "darksun-view-hp-psi-labels", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v66b"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[VIEW_HP_SITE, VIEW_HP_SITE + LABEL_ZONE_LEN],
                                  [VIEW_PSI_SITE, VIEW_PSI_SITE + LABEL_ZONE_LEN]],
                "overlay_index": 48,
                "overlay_continuation_ips": [VIEW_HP_CONTINUATION_IP, VIEW_PSI_CONTINUATION_IP],
                "main_mz_relocations_added": 0},
            "font": {"sha256": sha256(font), "bytes": len(font), "label_ids": label_ids},
            "resource": {"sha256": sha256((target / "RESOURCE.GFF").read_bytes()), **verification},
            "scope": {"view_hp_label": "VIEW CHARACTER's own \"HP:\" -> \"生命:\", separate from v61's item-panel PSI/AC",
                "view_psi_label": "VIEW CHARACTER's own \"PSI:\" -> \"靈能:\", matches v61's item-panel wording",
                "ac_label": "already Chinese on this screen -- shares v61's sprintf'd \"AC: %2d\" format string",
                "class_level_exp_hp_psi_numbers": "not in this candidate, still pending (see re_88)"},
            "preserved_parent_files": preserved}
        (build / "build-view-hp-psi-labels-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V67-READ-ME.txt").write_text(
            "v67: VIEW CHARACTER's own \"HP:\" and \"PSI:\" labels translated to\n"
            "\"生命:\" and \"靈能:\". These are separate literals from v61's item-panel\n"
            "AC:/PSI: labels (different call site, different argument shape) so they\n"
            "get their own view_hp_*/view_psi_* redirect rather than reusing v61's\n"
            "ac_label_entry/psi_label_entry. AC: needed no new patch here -- it\n"
            "already renders as \"防禦:\" because the item panel's copy is built via\n"
            "one shared sprintf format string that v61 already translated.\n"
            "The patch lives inside overlay unit 48 (same one v60's hover-name\n"
            "patch already uses) via the 14-byte DS-relative redirect, since this\n"
            "overlay's runtime segment is not stable across redraws -- a plain\n"
            "self-relative stub would have needed 22 bytes we didn't have room for\n"
            "anyway. The HP/PSI *numbers*, level, class, EXP, and AC/DAM numbers are\n"
            "unchanged -- see re_88 for the survey of what's left. Runtime\n"
            "validation NOT performed by this script.\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V66B_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
