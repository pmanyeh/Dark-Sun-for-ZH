#!/usr/bin/env python3
"""Clone accepted v55 and build an isolated BACKPACK -> 背包 UI candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

try:
    from .audit_inventory_ui import V55_EXE, V55_SHA256, verify_sources
    from .build_name_slot_candidate_from_v33 import run
    from .cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, read_bank, glyph_record_for_id, verify_extracted_gff_chunks,
    )
    from .plan_name_slot_consumers import (
        FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, ds_relative_consumer_redirect_bytes,
    )
except ImportError:
    from audit_inventory_ui import V55_EXE, V55_SHA256, verify_sources
    from build_name_slot_candidate_from_v33 import run
    from cjk_localization_pipeline import (
        DEFAULT_GFF_CAT, load_mapping, read_bank, glyph_record_for_id, verify_extracted_gff_chunks,
    )
    from plan_name_slot_consumers import (
        FONT_CORE_PAYLOAD_OFFSET, assemble_name_slot_cache, ds_relative_consumer_redirect_bytes,
    )

ROOT = Path(__file__).resolve().parents[1]
WRAPPER_OFFSET = 0x6E111
WRAPPER_ORIGINAL = bytes.fromhex("55 8B EC 66 FF 76 06 68 06 2C 66 FF 36 A4 11")
WRAPPER_REDIRECT = ds_relative_consumer_redirect_bytes(0x23A0) + b"\x90"
V55_RESOURCE_SHA256 = "d42018652b79f4231baa70610235fcded048520a4aa3cfaf419849c07b527470"
V55_FONT_SHA256 = "58ccce202250f47306b65663df45faf73be6bdb335b84ca5b65eb797ecde0321"
DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v56_backpack_ui"


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != V55_SHA256:
        raise ValueError("source EXE is not accepted v55")
    verify_sources(image)
    if image[WRAPPER_OFFSET:WRAPPER_OFFSET + 15] != WRAPPER_ORIGINAL:
        raise ValueError("bottom-label wrapper signature differs")
    result = bytearray(image)
    result[WRAPPER_OFFSET:WRAPPER_OFFSET + 15] = WRAPPER_REDIRECT
    if result[:WRAPPER_OFFSET] != image[:WRAPPER_OFFSET] or result[WRAPPER_OFFSET + 15:] != image[WRAPPER_OFFSET + 15:]:
        raise AssertionError("unexpected EXE edit outside wrapper")
    return bytes(result)


def patch_font(font: bytes, ids: tuple[int, int]) -> bytes:
    if sha256(font) != V55_FONT_SHA256:
        raise ValueError("source FONT is not accepted v55")
    if font[FONT_CORE_PAYLOAD_OFFSET:] != assemble_name_slot_cache():
        raise ValueError("default NAME core no longer reproduces v55")
    return font[:FONT_CORE_PAYLOAD_OFFSET] + assemble_name_slot_cache(backpack_ids=ids)


def build_candidate(source: Path, output: Path, gff_cat: Path = DEFAULT_GFF_CAT) -> dict[str, object]:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside the v55 source")
    game = source / "GAME/DARKSUN"
    exe = (game / "DSUN.EXE").read_bytes()
    resource = (game / "RESOURCE.GFF").read_bytes()
    if sha256(resource) != V55_RESOURCE_SHA256:
        raise ValueError("source RESOURCE is not accepted v55")
    patched_exe = patch_executable(exe)
    mapping = load_mapping(ROOT / "localization/cjk_mapping.json")
    by_char = {e["character"]: e["id"] for e in mapping["entries"]}
    ids = (by_char["背"], by_char["包"])
    banks = {i: read_bank((game / f"C{i}").read_bytes(), i) for i in range(6)}
    for value in ids:
        record = glyph_record_for_id(value, banks)
        if len(record) != 102 or record[:2] != b"\x0a\x00":
            raise ValueError("backpack glyph is not a 10x10 record")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="backpack-ui-v56-", dir=output.parent) as temporary:
        work = Path(temporary)
        build = work / "build"
        shutil.copytree(source, build)
        target_game = build / "GAME/DARKSUN"
        extracted = work / "font.bin"
        run(gff_cat, "extract", game / "RESOURCE.GFF", "FONT", "100", "-o", extracted)
        font = patch_font(extracted.read_bytes(), ids)
        extracted.write_bytes(font)
        (target_game / "DSUN.EXE").write_bytes(patched_exe)
        run(gff_cat, "replace", game / "RESOURCE.GFF", "FONT", "100", extracted,
            "-o", target_game / "RESOURCE.GFF")
        run(gff_cat, "extract", game / "RESOURCE.GFF", "--all", "-o", work / "before")
        run(gff_cat, "extract", target_game / "RESOURCE.GFF", "--all", "-o", work / "after")
        verification = verify_extracted_gff_chunks(work / "before", work / "after", [
            {"kind": "FONT", "chunk_id": 100, "sha256": sha256(font), "encoded_byte_length": len(font)},
        ])
        # Includes launcher, configs, saves, banks and inherited metadata. The
        # dedicated v56 manifest below is authoritative, not the copied v33/v55 ones.
        preserved = 0
        for path in source.rglob("*"):
            relative = path.relative_to(source)
            if not path.is_file() or relative.as_posix() in {"GAME/DARKSUN/DSUN.EXE", "GAME/DARKSUN/RESOURCE.GFF"}:
                continue
            if path.read_bytes() != (build / relative).read_bytes():
                raise ValueError(f"unexpected copied file difference: {relative}")
            preserved += 1
        manifest = {
            "format": "darksun-fixed-backpack-ui-candidate", "version": 1,
            "validation": {"runtime_status": "not_run", "stable_parent": "v55", "candidate": True},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {"sha256": sha256(patched_exe), "changed_range": [WRAPPER_OFFSET, WRAPPER_OFFSET + 15],
                           "main_mz_relocations_added": 0, "right_panel_unchanged": True},
            "font": {"sha256": sha256(font), "bytes": len(font), "core_offset": FONT_CORE_PAYLOAD_OFFSET,
                     "glyph_records_unchanged": True, "backpack_ids": ids, "cache_key": 0xFFFE},
            "resource": {"sha256": sha256((target_game / "RESOURCE.GFF").read_bytes()), **verification},
            "preserved_parent_files": preserved,
            "notes": ["Only DS:1853 fixed-label calls are translated.",
                      "Existing bottom-label renderer and all v55 coordinates retained.",
                      "Copied older build manifests describe ancestors, not this candidate."],
        }
        (build / "build-backpack-ui-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (build / "V56-READ-ME.txt").write_text(
            "v56 BACKPACK -> Chinese single-line candidate. Runtime validation NOT performed.\n"
            "Use build-backpack-ui-manifest.json; other manifests were copied from ancestors.\n"
            "Run launch-dosbox-x.cmd. Check empty backpack slot hover, item hover, switching characters, and right-click details.\n",
            encoding="ascii",
        )
        # Publish only after validating, and never overwrite an existing candidate.
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V55_EXE.parents[2])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
