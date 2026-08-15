#!/usr/bin/env python3
"""Build an isolated, verified Dark Sun Chinese-display test installation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from .cjk_localization_pipeline import (
        DEFAULT_GFF_CAT,
        DEFAULT_MAPPING,
        DEFAULT_RESOURCE_GFF,
        glyph_record_for_id,
        load_mapping,
        mapping_fingerprint,
        read_bank,
        verify_extracted_gff_chunks,
    )
    from .font100_tool import Font100
    from .patch_dsun_scratch_cache import patch_executable
except ImportError:
    from cjk_localization_pipeline import (
        DEFAULT_GFF_CAT,
        DEFAULT_MAPPING,
        DEFAULT_RESOURCE_GFF,
        glyph_record_for_id,
        load_mapping,
        mapping_fingerprint,
        read_bank,
        verify_extracted_gff_chunks,
    )
    from font100_tool import Font100
    from patch_dsun_scratch_cache import patch_executable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME_DIR = DEFAULT_RESOURCE_GFF.parent
DEFAULT_DOSBOX_X = Path(r"D:\git\DOSBox-X-AI\dosbox-src\bin\x64\Release\dosbox-x.exe")
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_native_height_scratch_font(
    source: bytes, scratch: bytes, bank_height: int
) -> tuple[bytes, int]:
    """Append scratch without changing FONT metrics or inserting invalid padding."""
    font = Font100.parse(source)
    if font.count != 256:
        raise ValueError(f"expected a 256-glyph FONT, got {font.count}")
    if bank_height not in (font.height, font.height + 1):
        raise ValueError(
            f"refusing to change global FONT height {font.height}: CJK bank height "
            f"{bank_height} must match it or exceed it by exactly one independently drawn shadow row"
        )
    expected_record_bytes = 2 + int.from_bytes(scratch[:2], "little") * bank_height
    if len(scratch) != expected_record_bytes:
        raise ValueError(
            f"scratch record is {len(scratch)} bytes; width/height require {expected_record_bytes}"
        )
    scratch_offset = len(source)
    return source + scratch, scratch_offset


def run(*arguments: Path | str) -> None:
    subprocess.run([str(item) for item in arguments], check=True)


def write_launcher(path: Path, dosbox_x: Path) -> None:
    executable = str(dosbox_x) if dosbox_x.exists() else "dosbox-x.exe"
    path.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "DOSBOX_X={executable}"\r\n'
        'pushd "%~dp0"\r\n'
        '"%DOSBOX_X%" -conf base.conf -conf graphics.conf -conf game.conf\r\n'
        "set \"RESULT=%ERRORLEVEL%\"\r\n"
        "popd\r\n"
        "exit /b %RESULT%\r\n",
        encoding="ascii",
        newline="",
    )


def scale_graphics_config(payload: str, scale: int) -> str:
    """Set a 640x480 integer-scaled DOSBox-X window without touching the source config."""
    if scale not in (1, 2, 3):
        raise ValueError("window scale must be 1, 2, or 3")
    resolution = f"{640 * scale}x{480 * scale}"
    result, count = re.subn(
        r"(?m)^windowresolution\s*=\s*[^\r\n]+$",
        f"windowresolution={resolution}",
        payload,
        count=1,
    )
    if count != 1:
        raise ValueError("graphics.conf does not contain exactly one windowresolution setting")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--bank-package", type=Path, required=True)
    parser.add_argument("--spin-package", type=Path)
    parser.add_argument("--gpl-package", type=Path)
    parser.add_argument("--gff-cat", type=Path, default=DEFAULT_GFF_CAT)
    parser.add_argument("--dosbox-x", type=Path, default=DEFAULT_DOSBOX_X)
    parser.add_argument("--ebox-line-gap", type=int, default=0)
    parser.add_argument("--window-scale", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    game_dir = args.game_dir.resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    if not (game_dir / "DSUN.EXE").is_file() or not (game_dir / "RESOURCE.GFF").is_file():
        raise ValueError(f"not a Dark Sun game directory: {game_dir}")

    gpl_package: dict[str, object] | None = None
    gpl_payload: bytes | None = None
    if args.gpl_package:
        gpl_package = json.loads(args.gpl_package.read_text(encoding="utf-8"))
        if gpl_package.get("format") != "darksun-gpl-dialogue-patch" or gpl_package.get("version") != 1:
            raise ValueError(f"unsupported GPL dialogue package: {args.gpl_package}")
        source_gpl = game_dir / "GPLDATA.GFF"
        if sha256(source_gpl.read_bytes()) != gpl_package.get("source_sha256"):
            raise ValueError("GPL dialogue package was built from a different GPLDATA.GFF")
        gpl_file = args.gpl_package.parent / str(gpl_package.get("patched_file"))
        gpl_payload = gpl_file.read_bytes()
        if len(gpl_payload) != gpl_package.get("patched_bytes") or sha256(gpl_payload) != gpl_package.get("patched_sha256"):
            raise ValueError("GPL dialogue package payload does not match its manifest")

    mapping = load_mapping(args.mapping)
    bank_package = json.loads(args.bank_package.read_text(encoding="utf-8"))
    if bank_package.get("format") != "darksun-cjk-bank-set" or bank_package.get("version") != 1:
        raise ValueError(f"unsupported bank package: {args.bank_package}")
    if bank_package.get("mapping_fingerprint") != mapping_fingerprint(mapping):
        raise ValueError("bank package was built from a different CJK mapping")
    banks: dict[int, dict[str, object]] = {}
    bank_files: list[tuple[Path, str, bytes]] = []
    for item in bank_package.get("banks", []):
        bank_id = item["bank"]
        source = args.bank_package.parent / item["file"]
        payload = source.read_bytes()
        if len(payload) != item["bytes"] or sha256(payload) != item["sha256"]:
            raise ValueError(f"bank package hash mismatch: {source}")
        banks[bank_id] = read_bank(payload, bank_id)
        bank_files.append((source, f"C{bank_id}.BIN", payload))
    if sorted(banks) != [0, 1, 2, 3]:
        raise ValueError(f"display staging requires banks 0..3, found {sorted(banks)}")
    bank_heights = {bank["height"] for bank in banks.values()}
    if len(bank_heights) != 1:
        raise ValueError(f"CJB1 banks disagree on glyph height: {sorted(bank_heights)}")
    bank_height = bank_heights.pop()
    record_sizes = {
        len(record) for bank in banks.values() for record in bank["records"].values()
    }
    if len(record_sizes) != 1:
        raise ValueError(f"display cache requires fixed-size glyph records, found {sorted(record_sizes)}")
    record_bytes = record_sizes.pop()

    launcher_root = game_dir.parent.parent
    required_configs = [launcher_root / name for name in ("base.conf", "graphics.conf", "game.conf")]
    for path in required_configs:
        if not path.is_file():
            raise ValueError(f"missing original launcher configuration: {path}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="darksun-cjk-staging-", dir=output.parent) as temporary:
        staging = Path(temporary) / "build"
        staged_game = staging / "GAME" / "DARKSUN"
        shutil.copytree(game_dir, staged_game)
        for config in required_configs:
            shutil.copyfile(config, staging / config.name)
        graphics_path = staging / "graphics.conf"
        graphics_path.write_text(
            scale_graphics_config(graphics_path.read_text(encoding="utf-8"), args.window_scale),
            encoding="utf-8",
        )
        write_launcher(staging / "launch-dosbox-x.cmd", args.dosbox_x)

        original_exe = (game_dir / "DSUN.EXE").read_bytes()
        work = Path(temporary) / "work"
        work.mkdir()
        source_font = work / "FONT-100.source.bin"
        run(args.gff_cat, "extract", game_dir / "RESOURCE.GFF", "FONT", "100", "-o", source_font)
        scratch = glyph_record_for_id(255, banks)
        font_payload, scratch_offset = build_native_height_scratch_font(
            source_font.read_bytes(), scratch, bank_height
        )
        patched_exe, cache = patch_executable(
            original_exe,
            scratch_offset,
            record_bytes,
            args.ebox_line_gap,
            cjk_draw_height=bank_height,
        )
        (staged_game / "DSUN.EXE").write_bytes(patched_exe)
        for _, filename, payload in bank_files:
            (staged_game / filename).write_bytes(payload)
        if gpl_payload is not None:
            (staged_game / "GPLDATA.GFF").write_bytes(gpl_payload)
        font_file = work / "FONT-100.cjk-scratch.bin"
        font_file.write_bytes(font_payload)

        resource_before_font = game_dir / "RESOURCE.GFF"
        spin_records: list[dict[str, object]] = []
        if args.spin_package:
            spin_package = json.loads(args.spin_package.read_text(encoding="utf-8"))
            if spin_package.get("format") != "darksun-gff-text-replacements":
                raise ValueError(f"unsupported SPIN package: {args.spin_package}")
            spin_records = [
                item for item in spin_package.get("replacements", []) if item.get("container") == "RESOURCE.GFF"
            ]
            resource_before_font = work / "RESOURCE.spin.GFF"
            run(
                args.gff_cat,
                "pack-text",
                game_dir / "RESOURCE.GFF",
                args.spin_package.parent / "RESOURCE.GFF",
                "-o",
                resource_before_font,
            )
        final_resource = staged_game / "RESOURCE.GFF"
        run(
            args.gff_cat,
            "replace",
            resource_before_font,
            "FONT",
            "100",
            font_file,
            "-o",
            final_resource,
        )

        original_chunks, final_chunks = work / "original-chunks", work / "final-chunks"
        run(args.gff_cat, "extract", game_dir / "RESOURCE.GFF", "--all", "-o", original_chunks)
        run(args.gff_cat, "extract", final_resource, "--all", "-o", final_chunks)
        records = spin_records + [
            {
                "kind": "FONT",
                "chunk_id": 100,
                "sha256": sha256(font_payload),
                "encoded_byte_length": len(font_payload),
            }
        ]
        resource_verification = verify_extracted_gff_chunks(original_chunks, final_chunks, records)

        unchanged_files = 0
        for source in game_dir.iterdir():
            mutable_files = {"DSUN.EXE", "RESOURCE.GFF"}
            if gpl_payload is not None:
                mutable_files.add("GPLDATA.GFF")
            if not source.is_file() or source.name in mutable_files:
                continue
            target = staged_game / source.name
            if source.read_bytes() != target.read_bytes():
                raise ValueError(f"copied game file changed unexpectedly: {source.name}")
            unchanged_files += 1

        manifest = {
            "format": "darksun-cjk-display-staging",
            "version": 1,
            "source_game": str(game_dir),
            "mapping_fingerprint": mapping_fingerprint(mapping),
            "bank_package": str(args.bank_package),
            "spin_package": str(args.spin_package) if args.spin_package else None,
            "gpl_package": str(args.gpl_package) if args.gpl_package else None,
            "font": {
                "legacy_source_bytes": len(source_font.read_bytes()),
                "height": Font100.parse(source_font.read_bytes()).height,
                "cjk_draw_height": bank_height,
                "scratch_offset": scratch_offset,
                "scratch_seed_id": 255,
                "scratch_record_bytes": record_bytes,
                "bytes": len(font_payload),
                "sha256": sha256(font_payload),
            },
            "executable": {
                "source_sha256": sha256(original_exe),
                "patched_sha256": sha256(patched_exe),
                "cache_bytes": len(cache),
                "scratch_cache_runtime_range": "36AA:545A..5533",
                "scratch_cache_file_policy": "open-read-close per glyph",
                "ebox_base94_wrap": "relocation-safe three-byte token advance",
                "mz_relocation_overlap_guard": True,
                "ebox_layout_line_gap": args.ebox_line_gap,
                "ebox_ui_state_step": 5,
                "ebox_next_page_delta": -(5 - args.ebox_line_gap),
                "ebox_previous_page_policy": "five one-line attempts with native boundary rejection",
            },
            "resource": {
                "source_sha256": sha256((game_dir / "RESOURCE.GFF").read_bytes()),
                "patched_sha256": sha256(final_resource.read_bytes()),
                **resource_verification,
            },
            "gpldata": (
                {
                    "source_sha256": gpl_package["source_sha256"],
                    "patched_sha256": gpl_package["patched_sha256"],
                    "patched_chunks": len(gpl_package["chunks"]),
                    "patched_occurrences": len(gpl_package["edits"]),
                    **gpl_package["verification"],
                }
                if gpl_package is not None
                else None
            ),
            "banks": [
                {"file": filename, "bytes": len(payload), "sha256": sha256(payload)}
                for _, filename, payload in bank_files
            ],
            "unchanged_copied_game_files": unchanged_files,
            "launcher": {
                "file": "launch-dosbox-x.cmd",
                "uses_original_configs": [path.name for path in required_configs],
                "entrypoint": "DARKSUN.BAT",
                "cycles": "fixed 7000",
                "window_scale": args.window_scale,
                "window_resolution": f"{640 * args.window_scale}x{480 * args.window_scale}",
            },
        }
        (staging / "build-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        shutil.move(str(staging), str(output))

    print(f"staging={output}")
    print(f"patched_exe_sha256={manifest['executable']['patched_sha256']}")
    print(f"patched_resource_sha256={manifest['resource']['patched_sha256']}")
    print(f"target_resource_chunks={manifest['resource']['target_chunks']}")
    print(f"unchanged_resource_chunks={manifest['resource']['unchanged_non_target_chunks']}")
    print(f"launcher={output / 'launch-dosbox-x.cmd'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
