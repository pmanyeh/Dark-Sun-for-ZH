#!/usr/bin/env python3
"""Fail-closed preflight for an isolated v35 item-text staging directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

try:
    from .patch_dsun_cjk16_probe import CODE_BASE
    from .patch_dsun_scratch_cache import (
        ITEM_FORMAT_LOOP,
        ITEM_FORMAT_POST_HELPER,
        ITEM_FORMAT_WRAPPER,
        ITEM_TEXT_FILE_BASE,
        item_format_loop,
        item_format_post_helper,
        item_format_wrapper,
        mz_relocation_file_offsets,
    )
except ImportError:
    from patch_dsun_cjk16_probe import CODE_BASE
    from patch_dsun_scratch_cache import (
        ITEM_FORMAT_LOOP,
        ITEM_FORMAT_POST_HELPER,
        ITEM_FORMAT_WRAPPER,
        ITEM_TEXT_FILE_BASE,
        item_format_loop,
        item_format_post_helper,
        item_format_wrapper,
        mz_relocation_file_offsets,
    )


PROFILE = "v35 stack-preserved flag and 16-bit post-render source advance"
MARKER = "CANDIDATE-NOT-VALIDATED.txt"


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def game_directory(root: Path) -> Path:
    nested = root / "GAME" / "DARKSUN"
    return nested if nested.is_dir() else root


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_candidate(staging: Path, baseline: Path | None = None) -> dict[str, object]:
    staging = staging.resolve()
    game = game_directory(staging)
    manifest_path = staging / "build-manifest.json"
    require(manifest_path.is_file(), "candidate build-manifest.json is missing")
    require((staging / MARKER).is_file(), f"candidate marker {MARKER} is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("format") == "darksun-cjk-display-staging", "unsupported manifest")
    validation = manifest.get("validation")
    require(isinstance(validation, dict), "candidate validation metadata is missing")
    require(validation.get("candidate") is True, "manifest is not marked as a candidate")
    require(validation.get("runtime_status") == "not_run", "candidate runtime status is not not_run")
    require(validation.get("requires_preflight") is True, "candidate does not require preflight")
    executable = manifest.get("executable")
    require(isinstance(executable, dict), "manifest executable section is missing")
    require(executable.get("item_text_base94_wrap") == PROFILE, "not a v35 item-text candidate")

    base_conf = (staging / "base.conf").read_text(encoding="utf-8")
    match = re.search(r"(?m)^autolock\s*=\s*([^\r\n]+)$", base_conf)
    require(match is not None and match.group(1).strip().lower() == "false", "autolock must be false")

    exe_path = game / "DSUN.EXE"
    image = exe_path.read_bytes()
    require(sha256(image) == executable.get("patched_sha256"), "DSUN.EXE hash mismatch")
    expected_regions = {
        ITEM_TEXT_FILE_BASE + ITEM_FORMAT_LOOP: item_format_loop(),
        CODE_BASE + ITEM_FORMAT_POST_HELPER: item_format_post_helper(),
        CODE_BASE + ITEM_FORMAT_WRAPPER: item_format_wrapper(),
    }
    for offset, expected in expected_regions.items():
        require(image[offset : offset + len(expected)] == expected, f"machine code mismatch at 0x{offset:05X}")

    relocations = mz_relocation_file_offsets(image)
    required_relocations = {
        ITEM_TEXT_FILE_BASE + 0x02EE,
        ITEM_TEXT_FILE_BASE + 0x02F7,
    }
    require(required_relocations <= relocations, "v35 far-call relocation is missing")
    require(ITEM_TEXT_FILE_BASE + 0x02F3 not in relocations, "original FONT relocation was not removed")

    resource = manifest.get("resource")
    require(isinstance(resource, dict), "manifest resource section is missing")
    require(sha256((game / "RESOURCE.GFF").read_bytes()) == resource.get("patched_sha256"), "RESOURCE.GFF hash mismatch")
    gpldata = manifest.get("gpldata")
    if gpldata is not None:
        require(isinstance(gpldata, dict), "manifest gpldata section is invalid")
        require(sha256((game / "GPLDATA.GFF").read_bytes()) == gpldata.get("patched_sha256"), "GPLDATA.GFF hash mismatch")
    for bank in manifest.get("banks", []):
        payload = (game / str(bank["file"])).read_bytes()
        require(len(payload) == bank["bytes"] and sha256(payload) == bank["sha256"], f"bank {bank['file']} mismatch")

    saves = {}
    for name in ("DARKRUN.GFF", "CHARSAVE.GFF", "SAVE01.SAV"):
        payload = (game / name).read_bytes()
        saves[name] = {"bytes": len(payload), "sha256": sha256(payload)}
    require(saves["DARKRUN.GFF"]["sha256"] == saves["SAVE01.SAV"]["sha256"], "DARKRUN.GFF and SAVE01.SAV differ")

    load_image_diff_runs: list[tuple[int, int]] = []
    if baseline is not None:
        baseline_game = game_directory(baseline.resolve())
        baseline_image = (baseline_game / "DSUN.EXE").read_bytes()
        require(len(baseline_image) == len(image), "baseline DSUN.EXE size differs")
        header_bytes = struct.unpack_from("<H", image, 0x08)[0] * 16
        allowed = set()
        for offset, payload in expected_regions.items():
            allowed.update(range(offset, offset + len(payload)))
        unexpected = [
            index
            for index in range(header_bytes, len(image))
            if image[index] != baseline_image[index] and index not in allowed
        ]
        if unexpected:
            raise ValueError(f"unexpected load-image difference at 0x{unexpected[0]:05X}")
        differences = [
            index
            for index in range(header_bytes, len(image))
            if image[index] != baseline_image[index]
        ]
        for index in differences:
            if not load_image_diff_runs or index != load_image_diff_runs[-1][1] + 1:
                load_image_diff_runs.append((index, index))
            else:
                load_image_diff_runs[-1] = (load_image_diff_runs[-1][0], index)
        for name in ("RESOURCE.GFF", "GPLDATA.GFF", "C0", "C1", "C2", "C3", "C4", "C5"):
            require((game / name).read_bytes() == (baseline_game / name).read_bytes(), f"{name} differs from baseline")

    return {
        "staging": str(staging),
        "profile": PROFILE,
        "exe_sha256": sha256(image),
        "autolock": False,
        "relocations": [f"0x{item:05X}" for item in sorted(required_relocations)],
        "load_image_diff_runs": [f"0x{start:05X}..0x{end:05X}" for start, end in load_image_diff_runs],
        "saves": saves,
        "preflight": "passed",
        "runtime_status": "not_run",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_candidate(args.staging, args.baseline), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
