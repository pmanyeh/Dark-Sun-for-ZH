#!/usr/bin/env python3
"""Clone stable v33 into an isolated, not-yet-validated NAME-slot candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from .build_cjk_display_staging import set_mouse_autolock
    from .cjk_localization_pipeline import DEFAULT_GFF_CAT, verify_extracted_gff_chunks
    from .plan_name_slot_consumers import (
        FONT_CORE_PAYLOAD_OFFSET,
        assemble_name_slot_cache,
        build_in_memory_v37_name_slot_executable,
        build_in_memory_v33_name_slot_executable,
        consumer_segment_relocations,
    )
except ImportError:
    from build_cjk_display_staging import set_mouse_autolock
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, verify_extracted_gff_chunks
    from plan_name_slot_consumers import (
        FONT_CORE_PAYLOAD_OFFSET,
        assemble_name_slot_cache,
        build_in_memory_v37_name_slot_executable,
        build_in_memory_v33_name_slot_executable,
        consumer_segment_relocations,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_V33 = ROOT / "scratch_test/cjk_display_staging_v33_dense_banks"
STAGING_OFFSET = 0x206B
RECORD_BYTES = 102
DYNAMIC_SLOTS = 7


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def run(*arguments: Path | str) -> None:
    subprocess.run([str(value) for value in arguments], check=True)


def expand_v33_font(current: bytes) -> tuple[bytes, tuple[int, ...]]:
    """Keep v33 staging intact and append seven persistent 10x10 records."""
    expected = STAGING_OFFSET + RECORD_BYTES
    if len(current) != expected:
        raise ValueError(f"v33 FONT is {len(current)} bytes, expected {expected}")
    staging = current[STAGING_OFFSET:]
    if int.from_bytes(staging[:2], "little") != 10 or len(staging) != RECORD_BYTES:
        raise ValueError("v33 FONT staging record is not the reviewed 10x10 layout")
    offsets = tuple(len(current) + index * RECORD_BYTES for index in range(DYNAMIC_SLOTS))
    return current + staging * DYNAMIC_SLOTS, offsets


def build_candidate(v33_root: Path, output: Path, gff_cat: Path) -> dict[str, object]:
    """Clone stable v33 and build the reviewed relocation-free v37 candidate."""
    return _build_candidate(v33_root, output, gff_cat)


def _build_candidate(v33_root: Path, output: Path, gff_cat: Path) -> dict[str, object]:
    v33_root = v33_root.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    source_game = v33_root / "GAME/DARKSUN"
    source_manifest_path = v33_root / "build-manifest.json"
    if not (source_game / "DSUN.EXE").is_file() or not source_manifest_path.is_file():
        raise ValueError(f"not a stable v33 staging root: {v33_root}")
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_exe = (source_game / "DSUN.EXE").read_bytes()
    if sha256(source_exe) != source_manifest["executable"]["patched_sha256"]:
        raise ValueError("v33 DSUN.EXE does not match its manifest")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="darksun-name-slots-v55-", dir=output.parent) as temporary:
        staging_root = Path(temporary) / "build"
        shutil.copytree(v33_root, staging_root)
        staged_game = staging_root / "GAME/DARKSUN"

        base_path = staging_root / "base.conf"
        base_path.write_text(
            set_mouse_autolock(base_path.read_text(encoding="utf-8"), False),
            encoding="utf-8",
        )

        work = Path(temporary) / "work"
        work.mkdir()
        current_font_path = work / "FONT-100.v33.bin"
        run(gff_cat, "extract", source_game / "RESOURCE.GFF", "FONT", "100", "-o", current_font_path)
        current_font = current_font_path.read_bytes()
        if sha256(current_font) != source_manifest["font"]["sha256"]:
            raise ValueError("v33 FONT-100 does not match its manifest")
        expanded_font, dynamic_offsets = expand_v33_font(current_font)
        core = assemble_name_slot_cache()
        expanded_font += core
        expanded_font_path = work / "FONT-100.name-slots.bin"
        expanded_font_path.write_bytes(expanded_font)

        patched_exe, verified_core = build_in_memory_v37_name_slot_executable(source_exe)
        if verified_core != core:
            raise ValueError("FONT-local NAME core assembly is not reproducible")
        (staged_game / "DSUN.EXE").write_bytes(patched_exe)
        final_resource = staged_game / "RESOURCE.GFF"
        run(gff_cat, "replace", source_game / "RESOURCE.GFF", "FONT", "100", expanded_font_path, "-o", final_resource)

        original_chunks = work / "original-chunks"
        final_chunks = work / "final-chunks"
        run(gff_cat, "extract", source_game / "RESOURCE.GFF", "--all", "-o", original_chunks)
        run(gff_cat, "extract", final_resource, "--all", "-o", final_chunks)
        verification = verify_extracted_gff_chunks(
            original_chunks,
            final_chunks,
            [{"kind": "FONT", "chunk_id": 100, "sha256": sha256(expanded_font), "encoded_byte_length": len(expanded_font)}],
        )

        preserved_files = 0
        for source in source_game.iterdir():
            if not source.is_file() or source.name in {"DSUN.EXE", "RESOURCE.GFF"}:
                continue
            if source.read_bytes() != (staged_game / source.name).read_bytes():
                raise ValueError(f"v33 file changed unexpectedly: {source.name}")
            preserved_files += 1

        manifest: dict[str, object] = {
            "format": "darksun-cjk-name-slot-candidate",
            "version": 3,
            "validation": {"candidate": True, "runtime_status": "not_run", "stable_parent": "v33_dense_banks", "design": "v55_shift_complete_item_panel_up_30px"},
            "parent": {"root": str(v33_root), "manifest_sha256": sha256(source_manifest_path.read_bytes()), "executable_sha256": sha256(source_exe), "resource_sha256": sha256((source_game / "RESOURCE.GFF").read_bytes())},
            "font": {"v33_bytes": len(current_font), "staging_offset": STAGING_OFFSET, "record_bytes": RECORD_BYTES, "dynamic_codes": [0x22, 0x23, 0x26, 0x3C, 0x3E, 0x5C, 0x7E], "dynamic_offsets": list(dynamic_offsets), "name_cache_core_offset": FONT_CORE_PAYLOAD_OFFSET, "runtime_base_offset": 4, "name_cache_core_bytes": len(core), "bytes": len(expanded_font), "sha256": sha256(expanded_font)},
            "executable": {"bytes": len(patched_exe), "sha256": sha256(patched_exe), "name_cache_core_bytes": len(core), "name_cache_core_sha256": sha256(core), "main_mz_relocations_added": 0},
            "resource": {"sha256": sha256(final_resource.read_bytes()), **verification},
            "preserved_v33_game_files": preserved_files,
            "launcher": {"mouse_autolock": False},
        }
        (staging_root / "build-name-slot-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staging_root / "CANDIDATE-NOT-VALIDATED.txt").write_text(
            "Dark Sun v55 complete item-panel block shifted upward 30px\nRuntime validation has NOT been performed.\nStable v33 was cloned and remains untouched.\nMouse autolock is disabled.\n",
            encoding="ascii",
        )
        shutil.move(str(staging_root), str(output))
    return manifest


def _build_rejected_v36_candidate(
    v33_root: Path, output: Path, gff_cat: Path
) -> dict[str, object]:
    """Preserve the rejected build recipe for forensic comparison only."""
    v33_root = v33_root.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    source_game = v33_root / "GAME/DARKSUN"
    source_manifest_path = v33_root / "build-manifest.json"
    if not (source_game / "DSUN.EXE").is_file() or not source_manifest_path.is_file():
        raise ValueError(f"not a stable v33 staging root: {v33_root}")
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_exe = (source_game / "DSUN.EXE").read_bytes()
    if sha256(source_exe) != source_manifest["executable"]["patched_sha256"]:
        raise ValueError("v33 DSUN.EXE does not match its manifest")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="darksun-name-slots-", dir=output.parent) as temporary:
        staging_root = Path(temporary) / "build"
        shutil.copytree(v33_root, staging_root)
        staged_game = staging_root / "GAME/DARKSUN"

        base_path = staging_root / "base.conf"
        base_path.write_text(
            set_mouse_autolock(base_path.read_text(encoding="utf-8"), False),
            encoding="utf-8",
        )

        work = Path(temporary) / "work"
        work.mkdir()
        current_font_path = work / "FONT-100.v33.bin"
        run(
            gff_cat,
            "extract",
            source_game / "RESOURCE.GFF",
            "FONT",
            "100",
            "-o",
            current_font_path,
        )
        current_font = current_font_path.read_bytes()
        if sha256(current_font) != source_manifest["font"]["sha256"]:
            raise ValueError("v33 FONT-100 does not match its manifest")
        expanded_font, dynamic_offsets = expand_v33_font(current_font)
        expanded_font_path = work / "FONT-100.name-slots.bin"
        expanded_font_path.write_bytes(expanded_font)

        patched_exe, core = build_in_memory_v33_name_slot_executable(source_exe)
        (staged_game / "DSUN.EXE").write_bytes(patched_exe)
        final_resource = staged_game / "RESOURCE.GFF"
        run(
            gff_cat,
            "replace",
            source_game / "RESOURCE.GFF",
            "FONT",
            "100",
            expanded_font_path,
            "-o",
            final_resource,
        )

        original_chunks = work / "original-chunks"
        final_chunks = work / "final-chunks"
        run(gff_cat, "extract", source_game / "RESOURCE.GFF", "--all", "-o", original_chunks)
        run(gff_cat, "extract", final_resource, "--all", "-o", final_chunks)
        verification = verify_extracted_gff_chunks(
            original_chunks,
            final_chunks,
            [
                {
                    "kind": "FONT",
                    "chunk_id": 100,
                    "sha256": sha256(expanded_font),
                    "encoded_byte_length": len(expanded_font),
                }
            ],
        )

        preserved_files = 0
        for source in source_game.iterdir():
            if not source.is_file() or source.name in {"DSUN.EXE", "RESOURCE.GFF"}:
                continue
            if source.read_bytes() != (staged_game / source.name).read_bytes():
                raise ValueError(f"v33 file changed unexpectedly: {source.name}")
            preserved_files += 1

        manifest: dict[str, object] = {
            "format": "darksun-cjk-name-slot-candidate",
            "version": 1,
            "validation": {
                "candidate": True,
                "runtime_status": "not_run",
                "stable_parent": "v33_dense_banks",
            },
            "parent": {
                "root": str(v33_root),
                "manifest_sha256": sha256(source_manifest_path.read_bytes()),
                "executable_sha256": sha256(source_exe),
                "resource_sha256": sha256((source_game / "RESOURCE.GFF").read_bytes()),
            },
            "font": {
                "v33_bytes": len(current_font),
                "staging_offset": STAGING_OFFSET,
                "record_bytes": RECORD_BYTES,
                "dynamic_codes": list(range(1, 8)),
                "dynamic_offsets": list(dynamic_offsets),
                "bytes": len(expanded_font),
                "sha256": sha256(expanded_font),
            },
            "executable": {
                "bytes": len(patched_exe),
                "sha256": sha256(patched_exe),
                "name_cache_core_bytes": len(core),
                "name_cache_core_sha256": sha256(core),
                "consumer_segment_relocations": sorted(consumer_segment_relocations()),
            },
            "resource": {
                "sha256": sha256(final_resource.read_bytes()),
                **verification,
            },
            "preserved_v33_game_files": preserved_files,
            "launcher": {"mouse_autolock": False},
        }
        (staging_root / "build-name-slot-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (staging_root / "CANDIDATE-NOT-VALIDATED.txt").write_text(
            "Dark Sun v36 NAME-slot cache candidate\n"
            "Runtime validation has NOT been performed.\n"
            "Stable v33 was cloned and remains untouched.\n"
            "Mouse autolock is disabled.\n",
            encoding="ascii",
        )
        shutil.move(str(staging_root), str(output))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v33-root", type=Path, default=DEFAULT_V33)
    parser.add_argument("--gff-cat", type=Path, default=DEFAULT_GFF_CAT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_candidate(args.v33_root, args.output, args.gff_cat)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
