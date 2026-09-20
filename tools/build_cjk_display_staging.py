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
from collections.abc import Sequence

try:
    from .cjk_localization_pipeline import (
        DEFAULT_GFF_CAT,
        DEFAULT_MAPPING,
        DEFAULT_RESOURCE_GFF,
        TRIPLE_BASE,
        TRIPLE_DIGIT_MIN,
        TRIPLE_PREFIX,
        glyph_record_for_id,
        load_mapping,
        mapping_fingerprint,
        read_bank,
        verify_extracted_gff_chunks,
    )
    from .font100_tool import Font100
    from .patch_dialogue_menu_wind import patch_dialogue_choice_paging, patch_dialogue_menu_wind
    from .patch_dsun_scratch_cache import patch_executable
except ImportError:
    from cjk_localization_pipeline import (
        DEFAULT_GFF_CAT,
        DEFAULT_MAPPING,
        DEFAULT_RESOURCE_GFF,
        TRIPLE_BASE,
        TRIPLE_DIGIT_MIN,
        TRIPLE_PREFIX,
        glyph_record_for_id,
        load_mapping,
        mapping_fingerprint,
        read_bank,
        verify_extracted_gff_chunks,
    )
    from font100_tool import Font100
    from patch_dialogue_menu_wind import patch_dialogue_choice_paging, patch_dialogue_menu_wind
    from patch_dsun_scratch_cache import patch_executable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME_DIR = DEFAULT_RESOURCE_GFF.parent
DEFAULT_DOSBOX_X = Path(r"D:\git\DOSBox-X-AI\dosbox-src\bin\x64\Release\dosbox-x.exe")
FONT100_OFFSET_TABLE = 8 + 256


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_native_height_scratch_font(
    source: bytes, scratch: bytes, bank_height: int
) -> tuple[bytes, int]:
    """Append scratch without changing FONT metrics or inserting invalid padding."""
    payload, offsets = build_native_height_scratch_font_slots(
        source, (scratch,), bank_height
    )
    return payload, offsets[0]


def build_native_height_scratch_font_slots(
    source: bytes, scratches: Sequence[bytes], bank_height: int
) -> tuple[bytes, tuple[int, ...]]:
    """Append verified fixed-height scratch records and return their offsets.

    The legacy 256-entry offset table is intentionally left unchanged on disk;
    the runtime loader redirects selected control-byte entries to these records.
    Keeping this operation append-only preserves every original FONT byte.
    """
    font = Font100.parse(source)
    if font.count != 256:
        raise ValueError(f"expected a 256-glyph FONT, got {font.count}")
    if bank_height not in (font.height, font.height + 1):
        raise ValueError(
            f"refusing to change global FONT height {font.height}: CJK bank height "
            f"{bank_height} must match it or exceed it by exactly one independently drawn shadow row"
        )
    if not scratches:
        raise ValueError("at least one scratch record is required")
    offsets: list[int] = []
    cursor = len(source)
    records: list[bytes] = []
    for index, scratch in enumerate(scratches):
        if len(scratch) < 2:
            raise ValueError(f"scratch record {index} is shorter than its width field")
        expected_record_bytes = 2 + int.from_bytes(scratch[:2], "little") * bank_height
        if len(scratch) != expected_record_bytes:
            raise ValueError(
                f"scratch record {index} is {len(scratch)} bytes; width/height "
                f"require {expected_record_bytes}"
            )
        if cursor > 0xFFFF or cursor + len(scratch) > 0x10000:
            raise ValueError("scratch records exceed the 16-bit FONT payload range")
        offsets.append(cursor)
        records.append(scratch)
        cursor += len(scratch)
    return source + b"".join(records), tuple(offsets)


def plan_dynamic_font_slots(
    slot_codes: Sequence[int], scratch_offsets: Sequence[int]
) -> tuple[tuple[int, int, int], ...]:
    """Map safe one-byte glyph codes to FONT-100 offset-table entries.

    The existing renderer sign-extends each byte before indexing the 256-entry
    table, so dynamic slots must be non-NUL codes below 0x80.  Each returned
    tuple is ``(slot_code, table_entry_offset, scratch_record_offset)``.
    """
    if len(slot_codes) != len(scratch_offsets):
        raise ValueError("slot code and scratch offset counts do not match")
    if not slot_codes:
        raise ValueError("at least one dynamic slot is required")
    if len(set(slot_codes)) != len(slot_codes):
        raise ValueError("dynamic slot codes must be unique")
    plan: list[tuple[int, int, int]] = []
    for code, scratch_offset in zip(slot_codes, scratch_offsets):
        if not 1 <= code <= 0x7F:
            raise ValueError(
                f"dynamic slot code 0x{code:02X} must be in the safe range 0x01..0x7F"
            )
        if not 0 <= scratch_offset <= 0xFFFF:
            raise ValueError(
                f"scratch offset 0x{scratch_offset:X} exceeds the 16-bit FONT range"
            )
        plan.append(
            (code, FONT100_OFFSET_TABLE + code * 2, scratch_offset)
        )
    return tuple(plan)


def predecode_name_to_dynamic_slots(
    payload: bytes, slot_codes: Sequence[int] = tuple(range(1, 8))
) -> tuple[bytes, tuple[tuple[int, int], ...]]:
    """Replace printable CJK triples with reusable one-byte dynamic slots.

    Returns the renderer-facing byte string and ordered ``(slot_code, cjk_id)``
    bindings. Repeated CJK IDs reuse their first slot and therefore require no
    duplicate glyph load.
    """
    # Reuse the same safety checks as the FONT offset plan. Scratch offsets are
    # irrelevant here, so zero is only a validation placeholder.
    plan_dynamic_font_slots(slot_codes, (0,) * len(slot_codes))
    output = bytearray()
    bindings: list[tuple[int, int]] = []
    slots_by_id: dict[int, int] = {}
    position = 0
    while position < len(payload):
        value = payload[position]
        if value == 0:
            raise ValueError("NAME payload must not include its NUL terminator")
        if value != TRIPLE_PREFIX:
            output.append(value)
            position += 1
            continue
        if position + 2 >= len(payload):
            raise ValueError(f"truncated printable CJK triple at byte {position}")
        high = payload[position + 1] - TRIPLE_DIGIT_MIN
        low = payload[position + 2] - TRIPLE_DIGIT_MIN
        if not 0 <= high < TRIPLE_BASE or not 0 <= low < TRIPLE_BASE:
            raise ValueError(f"invalid printable CJK triple at byte {position}")
        cjk_id = high * TRIPLE_BASE + low
        slot = slots_by_id.get(cjk_id)
        if slot is None:
            if len(bindings) >= len(slot_codes):
                raise ValueError(
                    f"NAME requires more than {len(slot_codes)} distinct dynamic glyph slots"
                )
            slot = slot_codes[len(bindings)]
            slots_by_id[cjk_id] = slot
            bindings.append((slot, cjk_id))
        output.append(slot)
        position += 3
    return bytes(output), tuple(bindings)


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


def set_mouse_autolock(payload: str, enabled: bool) -> str:
    """Set the SDL mouse lock policy without changing the source config."""
    value = "true" if enabled else "false"
    result, count = re.subn(
        r"(?m)^autolock\s*=\s*[^\r\n]+$",
        f"autolock={value}",
        payload,
        count=1,
    )
    if count != 1:
        raise ValueError("base.conf does not contain exactly one autolock setting")
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
    parser.add_argument("--menu-line-gap", type=int, default=2)
    parser.add_argument(
        "--dialogue-option-pitch",
        type=int,
        help="four dialogue choices per page at 11-pixel pitch with working MORE paging",
    )
    parser.add_argument(
        "--experimental-item-text-fix",
        action="store_true",
        help="rejected v34 post-render %%Fs experiment (build is refused)",
    )
    parser.add_argument(
        "--experimental-item-text-fix-v35",
        action="store_true",
        help="rejected v35 stack-preserved %%Fs experiment (build is refused)",
    )
    parser.add_argument("--window-scale", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument(
        "--mouse-autolock",
        action="store_true",
        help="lock the mouse on click for explicit automated-control sessions (default: false)",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.experimental_item_text_fix:
        raise ValueError(
            "the v34 post-render %Fs experiment is rejected: item text disappears "
            "and repeated item-info use crashes the game"
        )
    if args.experimental_item_text_fix_v35:
        raise ValueError(
            "the v35 stack-preserved %Fs experiment is rejected: the guest keeps "
            "running but the game enters a non-updating loop after loading"
        )

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
        bank_files.append((source, f"C{bank_id}", payload))
    bank_count = len(banks)
    if sorted(banks) != list(range(bank_count)):
        raise ValueError(f"display staging requires contiguous banks starting at 0, found {sorted(banks)}")
    if not 1 <= bank_count <= 9:
        raise ValueError(f"display staging requires 1..9 banks (single-digit CJB1 filenames), found {bank_count}")
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
        base_path = staging / "base.conf"
        base_path.write_text(
            set_mouse_autolock(
                base_path.read_text(encoding="utf-8"), args.mouse_autolock
            ),
            encoding="utf-8",
        )
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
            bank_count=bank_count,
            experimental_item_text_fix=args.experimental_item_text_fix_v35,
            menu_line_gap=args.menu_line_gap,
        )
        if args.dialogue_option_pitch is not None:
            patched_exe = patch_dialogue_choice_paging(patched_exe)
        (staged_game / "DSUN.EXE").write_bytes(patched_exe)
        for _, filename, payload in bank_files:
            (staged_game / filename).write_bytes(payload)
        gpl_abi_constraint: dict[str, object] | None = None
        if gpl_payload is not None:
            (staged_game / "GPLDATA.GFF").write_bytes(gpl_payload)
            declared_constraint = gpl_package.get("abi_constraint")
            if declared_constraint is not None:
                if not isinstance(declared_constraint, dict):
                    raise ValueError("GPL dialogue package abi_constraint must be an object")
                try:
                    kind = str(declared_constraint["chunk"])
                    offset = int(declared_constraint["external_entry_offset"])
                    opcode = int(declared_constraint["required_opcode"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("GPL dialogue package has an invalid abi_constraint") from exc
                if kind != "GPL-3" or offset < 0 or not 0 <= opcode <= 0xFF:
                    raise ValueError("unsupported GPL dialogue package abi_constraint")
                abi_chunk = work / "GPL-3.abi-check.bin"
                run(args.gff_cat, "extract", staged_game / "GPLDATA.GFF", "GPL", "3", "-o", abi_chunk)
                payload = abi_chunk.read_bytes()
                actual = payload[offset] if offset < len(payload) else None
                if actual != opcode:
                    found = "past end of chunk" if actual is None else f"0x{actual:02X}"
                    raise ValueError(
                        f"GPL-3 ABI entry 0x{offset:04X} must be 0x{opcode:02X}, found {found}"
                    )
                gpl_abi_constraint = {
                    **declared_constraint,
                    "verified_chunk_bytes": len(payload),
                }
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
        resource_after_font = (
            work / "RESOURCE.font.GFF"
            if args.dialogue_option_pitch is not None
            else staged_game / "RESOURCE.GFF"
        )
        run(
            args.gff_cat,
            "replace",
            resource_before_font,
            "FONT",
            "100",
            font_file,
            "-o",
            resource_after_font,
        )
        dialogue_wind: bytes | None = None
        final_resource = staged_game / "RESOURCE.GFF"
        if args.dialogue_option_pitch is not None:
            original_wind = work / "WIND-3008.original.bin"
            run(args.gff_cat, "extract", game_dir / "RESOURCE.GFF", "WIND", "3008", "-o", original_wind)
            dialogue_wind = patch_dialogue_menu_wind(
                original_wind.read_bytes(), args.dialogue_option_pitch
            )
            patched_wind = work / "WIND-3008.dialogue-options.bin"
            patched_wind.write_bytes(dialogue_wind)
            run(
                args.gff_cat,
                "replace",
                resource_after_font,
                "WIND",
                "3008",
                patched_wind,
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
        if dialogue_wind is not None:
            records.append(
                {
                    "kind": "WIND",
                    "chunk_id": 3008,
                    "sha256": sha256(dialogue_wind),
                    "encoded_byte_length": len(dialogue_wind),
                }
            )
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
            "validation": {
                "candidate": args.experimental_item_text_fix_v35,
                "runtime_status": (
                    "not_run" if args.experimental_item_text_fix_v35 else "baseline"
                ),
                "requires_preflight": args.experimental_item_text_fix_v35,
            },
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
                "bank_count": bank_count,
                "scratch_cache_runtime_range": "36AA:545A..5533",
                "scratch_cache_file_policy": "open-read-close per glyph",
                "ebox_base94_wrap": "relocation-safe three-byte token advance",
                "item_text_base94_wrap": (
                    "v35 stack-preserved flag and 16-bit post-render source advance"
                    if args.experimental_item_text_fix_v35
                    else "disabled"
                ),
                "mz_relocation_overlap_guard": True,
                "ebox_layout_line_gap": args.ebox_line_gap,
                "ebox_ui_state_step": 5,
                "ebox_next_page_delta": -(5 - args.ebox_line_gap),
                "ebox_previous_page_policy": "five one-line attempts with native boundary rejection",
                "menu_layout_line_gap": args.menu_line_gap,
            },
            "dialogue_options": (
                {
                    "resource_chunk": "WIND-3008",
                    "choice_pitch": args.dialogue_option_pitch,
                    "choice_slots": 4,
                    "window_height": 58,
                    "paging": "four choices per page; MORE, back page and fifth choice verified in game",
                    "sha256": sha256(dialogue_wind),
                }
                if dialogue_wind is not None else None
            ),
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
                    "abi_constraint": gpl_abi_constraint,
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
                "mouse_autolock": args.mouse_autolock,
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
        if args.experimental_item_text_fix_v35:
            (staging / "CANDIDATE-NOT-VALIDATED.txt").write_text(
                "Dark Sun v35 item-text candidate\n"
                "Runtime validation has NOT been performed.\n"
                "Run tools/verify_cjk_item_candidate.py before launching.\n"
                "Do not replace the stable v33 staging directory.\n",
                encoding="ascii",
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
