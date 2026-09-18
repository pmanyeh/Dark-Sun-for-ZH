#!/usr/bin/env python3
"""Build v68c: VIEW CHARACTER class names translated for 1/2/3-class parties.

Extends the live-validated `build_view_class_names_slot1_candidate.py`
(v68b, confirmed working for GERAKIS's single "Gladiator" -> "角鬥士")
to the two remaining code paths inside the same overlay-loaded class-name
draw function (`5B7C:2DC1` in the v67-era build, overlay 25, file_start
`0x6FDD0`): the two-class path (`5B7C:2EC9`) and the three-class path
(`5B7C:2E56`), confirmed live with K'RATCHEK (Fighter/Druid/Psionic),
CERMAK (Preserver/Gladiator) and CILLA (Preserver/Druid/Thief) all still
showing English before this candidate.

Each of the three draw paths independently repeats the same "read one
class slot from the identity record, look it up in the English table,
push a far pointer" 17-byte instruction span once per slot it draws (1
class = 1 repetition, 2 classes = 2, 3 classes = 3), so the total is 6
distinct EXE patch sites, not 3: slot 1 appears in all three paths, slot
2 in the two- and three-class paths, and slot 3 only in the three-class
path. All 6 share the same trick as `re_89`'s HP:/PSI: labels and v68b's
own single-class fix -- a 3-byte `mov ax,<slot tag>` plus the 14-byte
DS-relative redirect -- reusing v68b's three FONT-local entry points
(`class_slot1_label_entry`/`class_slot2_label_entry`/
`class_slot3_label_entry`, tags 0xFF90/0xFF91/0xFF92) since each slot's
record offset and lookup logic is identical regardless of which draw
path it's read from; only the continuation IP differs per site.

No FONT/mapping changes beyond v68b's -- same 8 class names, same six
new bank-5 glyphs.
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

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v68c_view_class_names_full"
V68B_ROOT = ROOT / "scratch_test/cjk_display_staging_v68b_view_class_names_slot1"
PARENT_EXE_HASH = "78a7f1bab8b168f97bafc0b0574b9365ee3d5474010cbdd02c93b9a03b36f4d9"
PARENT_RESOURCE_HASH = "8406e80875998466b53bac6d97a65da5823473ba1f4372141c6fbf2b6e5056e2"
PARENT_FONT_HASH = "1583ae003f82062f13843f63c26eaf0714bccdfd4ebb5294467886afff9c4b24"

OVERLAY_25_FILE_START = 0x6FDD0
SITE_LEN = 17

CLASS_SLOT1_TAG = 0xFF90
CLASS_SLOT2_TAG = 0xFF91
CLASS_SLOT3_TAG = 0xFF92

# (name, tag, local IP, original bytes) -- v68b already patched the
# single-class slot-1 site (local 0x2F1F); these are the five remaining.
SITES = [
    ("class2_slot2", CLASS_SLOT2_TAG, 0x2EC9, bytes.fromhex("c45e0a268a47229848c1e0028bd866ff30")),
    ("class2_slot1", CLASS_SLOT1_TAG, 0x2EE7, bytes.fromhex("8b5e0a268a47219848c1e0028bd866ff30")),
    ("class3_slot3", CLASS_SLOT3_TAG, 0x2E56, bytes.fromhex("c45e0a268a47239848c1e0028bd866ff30")),
    ("class3_slot2", CLASS_SLOT2_TAG, 0x2E72, bytes.fromhex("8b5e0a268a47229848c1e0028bd866ff30")),
    ("class3_slot1", CLASS_SLOT1_TAG, 0x2E90, bytes.fromhex("8b5e0a268a47219848c1e0028bd866ff30")),
]


def _tag_redirect(tag: int, continuation_ip: int) -> bytes:
    stub = bytes.fromhex("B8") + tag.to_bytes(2, "little") + ds_relative_consumer_redirect_bytes(continuation_ip)
    if len(stub) > SITE_LEN:
        raise ValueError("class name site redirect does not fit")
    return stub.ljust(SITE_LEN, b"\x90")


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v68b")
    ranges = []
    for name, tag, local_ip, original in SITES:
        file_off = OVERLAY_25_FILE_START + local_ip
        if image[file_off:file_off + SITE_LEN] != original:
            raise ValueError(f"{name} consumer differs")
        ranges.append((file_off, file_off + SITE_LEN))
    verify_overlay_relocations(image, ranges)
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    for name, tag, local_ip, original in SITES:
        file_off = OVERLAY_25_FILE_START + local_ip
        continuation_ip = local_ip + SITE_LEN
        result[file_off:file_off + SITE_LEN] = _tag_redirect(tag, continuation_ip)
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("class name patch changed main MZ relocations")
    allowed: set[int] = set()
    for _, _, local_ip, _ in SITES:
        file_off = OVERLAY_25_FILE_START + local_ip
        allowed |= set(range(file_off, file_off + SITE_LEN))
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
    with tempfile.TemporaryDirectory(prefix="view-class-names-full-v68c-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target = build / "GAME/DARKSUN"

        font_path = work / "font.bin"
        run(DEFAULT_GFF_CAT, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", font_path)
        original_font = font_path.read_bytes()
        if sha256(original_font) != PARENT_FONT_HASH:
            raise ValueError("v68b FONT does not match the reviewed pre-fanout font")
        # FONT is unchanged from v68b -- same three class_slotN entry points,
        # same class name table. Only the EXE gains the five extra redirects.
        (target / "DSUN.EXE").write_bytes(patched)
        preserved = 0
        for path in source.rglob("*"):
            rel = path.relative_to(source)
            if path.is_file() and rel.as_posix() != "GAME/DARKSUN/DSUN.EXE":
                if path.read_bytes() != (build / rel).read_bytes():
                    raise ValueError(f"unexpected copied file difference: {rel}")
                preserved += 1
        manifest = {"format": "darksun-view-class-names-full", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v68b"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched),
                "patch_ranges": [[OVERLAY_25_FILE_START + local_ip, OVERLAY_25_FILE_START + local_ip + SITE_LEN]
                                  for _, _, local_ip, _ in SITES],
                "overlay_index": 25,
                "main_mz_relocations_added": 0},
            "resource": {"sha256": sha256(resource), "unchanged": True},
            "scope": {"class_names_all_paths": "1/2/3-class draw paths all translated (6 total patch "
                    "sites incl. v68b's single-class one)",
                "level_exp_dam": "not in this candidate, still pending (see re_88)"},
            "preserved_parent_files": preserved}
        (build / "build-view-class-names-full-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V68c-READ-ME.txt").write_text(
            "v68c: VIEW CHARACTER class names translated for 1/2/3-class parties\n"
            "(e.g. K'RATCHEK's \"Fighter/Druid/Psionic\", CERMAK's \"Preserver/\n"
            "Gladiator\", CILLA's \"Preserver/Druid/Thief\"), extending v68b's\n"
            "already-validated single-class fix to the two remaining draw paths.\n"
            "Level, EXP, and the DAM: label are not in this candidate -- see re_88.\n"
            "Runtime validation NOT performed by this script.\n",
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
