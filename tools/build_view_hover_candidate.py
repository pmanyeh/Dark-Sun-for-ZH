#!/usr/bin/env python3
"""Build isolated v60: decode VIEW CHARACTER equipment hover names."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

try:
    from .build_backpack_ui_candidate import ROOT, sha256
    from .build_view_character_candidate import verify_overlay_relocations
    from .build_view_interaction_candidate import DEFAULT_OUTPUT as V59_ROOT
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import (
        NAME_POINTER_SEQUENCE,
        ds_relative_consumer_redirect_bytes,
    )
except ImportError:
    from build_backpack_ui_candidate import ROOT, sha256
    from build_view_character_candidate import verify_overlay_relocations
    from build_view_interaction_candidate import DEFAULT_OUTPUT as V59_ROOT
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import (
        NAME_POINTER_SEQUENCE,
        ds_relative_consumer_redirect_bytes,
    )

DEFAULT_OUTPUT = ROOT / "scratch_test/cjk_display_staging_v60_view_hover_name"
PARENT_EXE_HASH = "9ac8f29f1a9525ca7f54a768a8c5501e23d8b22812e3c28275c8e09891b61990"
PARENT_RESOURCE_HASH = "e90624c5a677f8de3191ea9d68a493d19e7654c2a2bd5127510de237a9b156ef"
HOVER_SITE = 0x8A925
# Segment 48 begins at file offset 0x89E70. The replaced 14-byte sequence ends
# at overlay-local IP 0x0AC3, immediately before the original formatter args.
HOVER_CONTINUATION_IP = 0x0AC3


def patch_executable(image: bytes) -> bytes:
    if sha256(image) != PARENT_EXE_HASH:
        raise ValueError("source EXE is not v59")
    end = HOVER_SITE + len(NAME_POINTER_SEQUENCE)
    if image[HOVER_SITE:end] != NAME_POINTER_SEQUENCE:
        raise ValueError("VIEW hover NAME consumer differs")
    verify_overlay_relocations(image, [(HOVER_SITE, end)])
    replacement = ds_relative_consumer_redirect_bytes(HOVER_CONTINUATION_IP)
    if len(replacement) != len(NAME_POINTER_SEQUENCE):
        raise AssertionError("VIEW hover redirect changed instruction span")
    relocations = mz_relocation_file_offsets(image)
    result = bytearray(image)
    result[HOVER_SITE:end] = replacement
    patched = bytes(result)
    if mz_relocation_file_offsets(patched) != relocations:
        raise ValueError("VIEW hover patch changed main MZ relocations")
    allowed = set(range(HOVER_SITE, end))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(image, patched))):
        raise AssertionError("unexpected EXE difference")
    return patched


def build_candidate(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("output must be a new directory outside v59")
    game = source / "GAME/DARKSUN"
    exe_path, resource_path = game / "DSUN.EXE", game / "RESOURCE.GFF"
    exe, resource = exe_path.read_bytes(), resource_path.read_bytes()
    if sha256(resource) != PARENT_RESOURCE_HASH:
        raise ValueError("source RESOURCE is not v59")
    patched = patch_executable(exe)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="view-hover-v60-", dir=output.parent) as temporary:
        build = Path(temporary) / "build"
        shutil.copytree(source, build)
        (build / "GAME/DARKSUN/DSUN.EXE").write_bytes(patched)
        preserved = 0
        for path in source.rglob("*"):
            rel = path.relative_to(source)
            if path.is_file() and rel.as_posix() != "GAME/DARKSUN/DSUN.EXE":
                if path.read_bytes() != (build / rel).read_bytes():
                    raise ValueError(f"unexpected copied file difference: {rel}")
                preserved += 1
        manifest = {
            "format": "darksun-view-hover-name-candidate",
            "version": 1,
            "validation": {"runtime_status": "not_run", "hover_name_status": "pending"},
            "parent": {"root": str(source), "exe_sha256": sha256(exe), "resource_sha256": sha256(resource)},
            "executable": {
                "sha256": sha256(patched),
                "patch_range": [HOVER_SITE, HOVER_SITE + len(NAME_POINTER_SEQUENCE)],
                "overlay_index": 48,
                "overlay_continuation_ip": HOVER_CONTINUATION_IP,
                "main_mz_relocations_added": 0,
            },
            "resource": {"sha256": sha256(resource), "unchanged": True},
            "scope": {
                "view_equipment_hover_name": "NAME-slot decoded",
                "right_click_cards": "inherited from v59",
                "multiclass_lower_panel": "unchanged",
            },
            "preserved_parent_files": preserved,
        }
        (build / "build-view-hover-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (build / "V60-READ-ME.txt").write_text(
            "v60: decode VIEW CHARACTER equipment hover names through the existing NAME-slot cache.\n"
            "RESOURCE, layout, right-click handlers and lower character panel are unchanged.\n"
            "Runtime hover validation is still required.\n",
            encoding="ascii",
        )
        if output.exists():
            raise ValueError("output appeared during build")
        build.rename(output)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=V59_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
