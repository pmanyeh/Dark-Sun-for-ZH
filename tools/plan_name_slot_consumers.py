#!/usr/bin/env python3
"""Build and verify overlay-safe redirects for proven NAME-1 UI consumers."""

from __future__ import annotations

import runpy
import struct
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path


FONT_CORE_PAYLOAD_OFFSET = 0x239B
FONT_RUNTIME_BASE_OFFSET = 0x0004
DECODER_OFFSET = FONT_CORE_PAYLOAD_OFFSET + FONT_RUNTIME_BASE_OFFSET
REJECTED_RESIDENT_DECODER_OFFSET = 0x51F1
DECODER_LINK_SEGMENT = 0x2E86
HEIGHT_HELPER_OFFSET = 0x51F1
LEGACY_HEIGHT_HELPER = 0x53D6
RESIDENT_TRAMPOLINE_OFFSET = 0x5414
DGROUP_FILE_BASE = 0x48960
DGROUP_MAX_OFFSET = 0xA4BC
POINTER_CELL_OFFSET = 0x6100
CODE_FROM_DGROUP_DELTA = 0x14D0
ITEM_TEXT_FILE_BASE = 0x30BA0
ITEM_LINE_ADVANCE_PATCHES = {
    # v55 moves the complete right-side information block upward.  The first
    # site positions the static ability-label block; the second positions its
    # six numeric rows.  The following three sites position PSI/AC text and
    # values.  Together with the weapon origin below, these preserve the v52
    # relative layout while keeping the worst-case seven 10px attack rows
    # above the bottom controls.
    0x06F5A0: (
        bytes.fromhex("66 68 EC 00 35 00"),
        bytes.fromhex("66 68 EC 00 17 00"),
    ),
    0x06F5E7: (
        bytes.fromhex("6B C0 07 05 35 00"),
        bytes.fromhex("6B C0 07 05 17 00"),
    ),
    0x06F61A: (
        bytes.fromhex("66 68 EC 00 63 00"),
        bytes.fromhex("66 68 EC 00 45 00"),
    ),
    0x06F62D: (
        bytes.fromhex("66 68 19 01 63 00"),
        bytes.fromhex("66 68 19 01 45 00"),
    ),
    0x06F66E: (
        bytes.fromhex("66 68 EC 00 71 00"),
        bytes.fromhex("66 68 EC 00 53 00"),
    ),
    0x06F6A5: (
        bytes.fromhex("66 68 EC 00 78 00"),
        bytes.fromhex("66 68 EC 00 63 00"),
    ),
    0x072773: (bytes.fromhex("6B C0 07"), bytes.fromhex("6B C0 0A")),
    0x07296F: (bytes.fromhex("83 46 0E 07"), bytes.fromhex("83 46 0E 0A")),
    0x08BE7C: (bytes.fromhex("83 C7 07"), bytes.fromhex("83 C7 0A")),
    0x08BF3A: (bytes.fromhex("83 C7 07"), bytes.fromhex("83 C7 0A")),
    0x08C07D: (bytes.fromhex("83 C7 07"), bytes.fromhex("83 C7 0A")),
    0x08C0FB: (bytes.fromhex("83 C7 07"), bytes.fromhex("83 C7 0A")),
    0x08C132: (bytes.fromhex("6B C0 07"), bytes.fromhex("6B C0 0A")),
}
ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "tools/cjk_name_slot_cache.asm"
TOOLBIN = ROOT / ".tools/w64devkit/bin"
FIXED_UI_LABELS = ROOT / "localization/catalog/fixed_ui_labels.csv"
LEGACY_BANK_COUNT = 6

# Assembly tables filled from fixed_ui_labels.csv, in table order. The asm
# looks up gender (2 characters) and alignment (4 characters) by constant
# stride; the other tables go through offset tables and may vary in length.
UI_TEXT_TABLES = {
    # macro: (row style, stride-table label, fixed length, (row label, unit) rows)
    "ui_text_materials": ("label", None, None, (
        ("material_0", "UI_material_wooden"), ("material_1", "UI_material_bone"),
        ("material_2", "UI_material_stone"), ("material_3", "UI_material_obsidian"),
        ("material_4", "UI_material_metal"), ("material_5", "UI_material_leather"),
    )),
    "ui_text_genders": ("stride", "gender_sources", 2, (
        ("male", "UI_gender_male"), ("female", "UI_gender_female"),
    )),
    "ui_text_races": ("label", None, None, (
        ("race_0", "UI_race_human"), ("race_1", "UI_race_dwarf"),
        ("race_2", "UI_race_elf"), ("race_3", "UI_race_half_elf"),
        ("race_4", "UI_race_half_giant"), ("race_5", "UI_race_halfling"),
        ("race_6", "UI_race_mul"), ("race_7", "UI_race_thri_kreen"),
    )),
    "ui_text_alignments": ("stride", "alignment_sources", 4, (
        ("lg", "UI_alignment_lg"), ("ln", "UI_alignment_ln"), ("le", "UI_alignment_le"),
        ("ng", "UI_alignment_ng"), ("tn", "UI_alignment_tn"), ("ne", "UI_alignment_ne"),
        ("cg", "UI_alignment_cg"), ("cn", "UI_alignment_cn"), ("ce", "UI_alignment_ce"),
    )),
    "ui_text_classes": ("label", None, None, (
        ("class_cleric", "UI_class_cleric"), ("class_druid", "UI_class_druid"),
        ("class_fighter", "UI_class_fighter"), ("class_gladiator", "UI_class_gladiator"),
        ("class_preserver", "UI_class_preserver"), ("class_psionic", "UI_class_psionicist"),
        ("class_ranger", "UI_class_ranger"), ("class_thief", "UI_class_thief"),
    )),
    "ui_text_creation_titles": ("label", None, None, (
        ("creation_psi_title", "UI_creation_psi_title"),
        ("creation_sphere_title", "UI_creation_sphere_title"),
    )),
}
# name_buffer holds 24 decoded bytes and the pool has ten glyph slots.
UI_TEXT_MAX_CHARACTERS = 8
BACKPACK_UNITS = ("UI_backpack",)
ABILITY_UNITS = ("UI_ability_str", "UI_ability_dex", "UI_ability_con",
                 "UI_ability_int", "UI_ability_wis", "UI_ability_cha")
LABEL_UNITS = ("UI_label_ac", "UI_label_psi", "UI_view_label_hp", "UI_view_label_psi")


def load_fixed_ui_ids(
    mapping: dict[str, object], path: Path = FIXED_UI_LABELS
) -> dict[str, tuple[int, ...]]:
    """Resolve every fixed UI label to CJK IDs; ASCII is not allowed here."""
    import csv

    by_character = {entry["character"]: entry["id"] for entry in mapping["entries"]}
    result: dict[str, tuple[int, ...]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            text = row["translation_zh_tw"]
            missing = [character for character in text if character not in by_character]
            if missing:
                raise ValueError(f"{row['unit_id']}: {''.join(missing)!r} is not in the CJK mapping")
            result[row["unit_id"]] = tuple(by_character[character] for character in text)
    return result


def fixed_ui_pair_ids(ids: dict[str, tuple[int, ...]], units: Sequence[str]) -> tuple[int, ...]:
    """Flatten two-character labels in order, as the fixed-stride tables expect."""
    flattened: list[int] = []
    for unit in units:
        if len(ids[unit]) != 2:
            raise ValueError(f"{unit} must be exactly two characters for its fixed-stride table")
        flattened += ids[unit]
    return tuple(flattened)


def name_slot_ui_text_include(ids: dict[str, tuple[int, ...]]) -> str:
    """Return the ui_text_* macro definitions for cjk_name_slot_cache.asm."""

    def triples(values: Sequence[int]) -> str:
        return ", ".join(f"0x5E, {0x21 + value // 94}, {0x21 + value % 94}" for value in values)

    lines: list[str] = []
    for macro, (style, stride_label, length, rows) in UI_TEXT_TABLES.items():
        # Older label sets (e.g. the v57 IDs) predate some tables entirely;
        # only the decoder options that use such a table need it.
        if all(unit not in ids for _, unit in rows):
            continue
        lines.append(f".macro {macro}")
        if stride_label:
            lines.append(f"{stride_label}:")
        for label, unit in rows:
            values = ids[unit]
            if length is not None and len(values) != length:
                raise ValueError(f"{unit} must be exactly {length} characters")
            if not 1 <= len(values) <= UI_TEXT_MAX_CHARACTERS:
                raise ValueError(f"{unit} must be 1..{UI_TEXT_MAX_CHARACTERS} characters")
            if style == "label":
                lines.append(f"{label}: .byte {triples(values)}, 0")
            else:
                # identity_text pads two characters to 8 bytes and
                # alignment_text pads four characters to 16 bytes.
                padding = 2 if length == 2 else 4
                lines.append(f"    .byte {triples(values)}{', 0' * padding}")
        lines.append(".endm")
    return "\n".join(lines) + "\n"

# Bottom hover, right-click card, and the two right-side conditional branches.
PROVEN_CONSUMER_OFFSETS = (0x06E288, 0x072955, 0x08BECF, 0x08BF00)
CONSUMER_CONTINUATION_IPS = {
    0x06E288: 0x2516,
    0x072955: 0x2B93,
    0x08BECF: 0x0FFD,
    0x08BF00: 0x102E,
}

NAME_POINTER_SEQUENCE = bytes.fromhex(
    "6B C0 19 "       # imul ax, ax, 25
    "8B 16 6D 16 "    # mov dx, [NAME table offset]
    "03 D0 "          # add dx, ax
    "FF 36 6F 16 "    # push [NAME table segment]
    "52"              # push dx
)
NAME_HEIGHT_HELPER_SIGNATURE = bytes.fromhex(
    "B8 0A 00 80 7E 06 08 72 07 80 7E 06 7F 74 01 48 C3"
)
V33_HEIGHT_HELPER = bytes.fromhex("B8 09 00 80 7E 06 7F 75 01 40 C3")
POINTER_INITIALIZER_HEIGHT_HELPER = (
    bytes.fromhex("C7 06 00 61 14 54") + V33_HEIGHT_HELPER
)


def consumer_redirect_bytes(
    decoder_offset: int = REJECTED_RESIDENT_DECODER_OFFSET,
    decoder_link_segment: int = DECODER_LINK_SEGMENT,
) -> bytes:
    """Return an equal-length redirect; AX enters as NAME id, DX:AX returns."""
    if not 0 <= decoder_offset <= 0xFFFF:
        raise ValueError("decoder offset must fit u16")
    if not 0 <= decoder_link_segment <= 0xFFFF:
        raise ValueError("decoder link segment must fit u16")
    replacement = (
        b"\x9A"
        + struct.pack("<HH", decoder_offset, decoder_link_segment)
        + b"\x52\x50"  # original ABI stack order: segment, then offset
    )
    return replacement.ljust(len(NAME_POINTER_SEQUENCE), b"\x90")


def ds_relative_consumer_redirect_bytes(
    continuation_ip: int,
) -> bytes:
    """Return the v42 14-byte relocation-free overlay redirect.

    This synthesizes a far-call frame and transfers directly to the resident
    trampoline.  ``(DS-1000):0714`` aliases ``(DS-14D0):5414`` while allowing
    the segment adjustment to fit in three bytes.  No mutable DGROUP pointer is
    involved; the decoder leaves its returned DX:AX pointer on the stack.
    """
    if not 0 <= continuation_ip <= 0xFFFF:
        raise ValueError("continuation IP must fit u16")
    replacement = (
        b"\x0E\x68" + struct.pack("<H", continuation_ip)  # push cs; push return IP
        + b"\x8C\xDB\x80\xEF\x10"  # mov bx,ds; sub bh,10h
        + b"\x53\x68\x14\x07\xCB"  # push bx; push 0714h; retf
    )
    if len(replacement) != len(NAME_POINTER_SEQUENCE):
        raise AssertionError("DS-relative consumer redirect is not exactly 14 bytes")
    return replacement


def verify_proven_consumer_sites(
    image: bytes, offsets: Sequence[int] = PROVEN_CONSUMER_OFFSETS
) -> tuple[int, ...]:
    """Require every planned site to match v33 before any future mutation."""
    verified: list[int] = []
    for offset in offsets:
        actual = image[offset : offset + len(NAME_POINTER_SEQUENCE)]
        if actual != NAME_POINTER_SEQUENCE:
            raise ValueError(
                f"NAME consumer 0x{offset:05X} differs: {actual.hex()}"
            )
        verified.append(offset)
    return tuple(verified)


def verify_overlay_relocations(image: bytes, ranges: list[tuple[int, int]]) -> None:
    """Conservatively reject touching either byte of a Borland overlay fixup."""
    parser = runpy.run_path(str(ROOT / "vendor/opends/tools/ovr-map/ovr-map.py"))
    mz = parser["parse_mz"](image)
    fbov = parser["parse_fbov"](image, mz["image_end"])
    start = parser["find_table"](image, fbov["exeinfo"], mz["image_end"])
    segments = parser["parse_table"](image, start, mz["image_end"], fbov["overlay_base"])
    for segment in segments:
        relevant = [(a, b) for a, b in ranges if a < segment["file_end"] and b > segment["file_start"]]
        if not relevant:
            continue
        count = segment["relocation_count"]
        offsets = struct.unpack_from(f"<{count}H", image, segment["file_end"])
        for offset in offsets:
            site = segment["file_start"] + offset
            if any(a < site + 2 and b > site for a, b in relevant):
                raise ValueError(f"patch overlaps overlay relocation at 0x{site:X}")


def consumer_segment_relocations(
    offsets: Sequence[int] = PROVEN_CONSUMER_OFFSETS,
) -> frozenset[int]:
    """Return the segment words v36 wrongly treated as main-MZ relocations."""
    return frozenset(offset + 3 for offset in offsets)


def self_relative_tag_redirect(tag: int, span_len: int, *, skip_bytes: int | None = None) -> bytes:
    """Return the v57-style self-computing-IP redirect used for inline spans.

    Unlike ``ds_relative_consumer_redirect_bytes`` (which returns a decoded
    DX:AX pointer to a fixed, precomputed continuation IP), this variant lets
    the FONT-local entry point itself finish the call and choose when to
    return. The continuation IP is derived at runtime from the stub's own
    position (``call +0`` immediately popped), so the caller only supplies
    how many bytes of the original span are being replaced, not an absolute
    address.

    ``skip_bytes`` (default: ``span_len``) is the true distance from the
    start of this stub to the desired continuation. Pass it explicitly when
    ``span_len`` bytes are overwritten but a further, untouched run of bytes
    right after them must also be skipped -- e.g. because that run's own far
    call has an overlay-relocated segment word that must never be patched.
    """
    if not 0 <= tag <= 0xFFFF:
        raise ValueError("tag must fit u16")
    if span_len < 22:
        raise ValueError("self-relative tag redirect needs at least 22 bytes")
    skip = span_len if skip_bytes is None else skip_bytes
    if skip < span_len:
        raise ValueError("skip_bytes must be at least span_len")
    stub = bytes.fromhex("0E E8 00 00 58 05") + struct.pack("<H", skip - 4)
    stub += b"\x50\xB8" + struct.pack("<H", tag) + bytes.fromhex("8C DB 80 EF 10 53 68 14 07 CB")
    if len(stub) > span_len:
        raise ValueError("self-relative tag redirect does not fit")
    return stub.ljust(span_len, b"\x90")


def height_helper_redirect(helper: bytes = NAME_HEIGHT_HELPER_SIGNATURE) -> bytes:
    """Redirect v33's helper to one of the reviewed 17-byte helpers."""
    if helper not in (NAME_HEIGHT_HELPER_SIGNATURE, POINTER_INITIALIZER_HEIGHT_HELPER):
        raise ValueError("extended height helper differs from reviewed bytes")
    displacement = HEIGHT_HELPER_OFFSET - (LEGACY_HEIGHT_HELPER + 3)
    if not -0x8000 <= displacement <= 0x7FFF:
        raise ValueError("extended height helper is outside near-jump range")
    return (b"\xE9" + struct.pack("<h", displacement)).ljust(
        len(V33_HEIGHT_HELPER), b"\x90"
    )


def assemble_name_slot_cache(
    staging_offset: int = 0x206B,
    first_slot_offset: int = 0x20D1,
    record_bytes: int = 102,
    *,
    backpack_ids: tuple[int, int] | None = None,
    ability_ids: tuple[int, ...] | None = None,
    view_character: bool = False,
    view_y_origin: int = 40,
    label_ids: tuple[int, int, int, int] | None = None,
    materials: bool = False,
    identity: bool = False,
    gender_position: tuple[int, int] | None = None,
    alignment_position: tuple[int, int] | None = None,
    class_names: bool = False,
    bank_count: int = LEGACY_BANK_COUNT,
    ui_text_ids: dict[str, tuple[int, ...]] | None = None,
    class_row: tuple[int, int] | None = None,
    stat_row_y: int | None = None,
    menu_titles: bool = False,
    status_texts: bool = False,
    text_draws: bool = False,
    scroll_texts: bool = False,
    cursor_hotkeys: bool = False,
    smart_cursor: bool = False,
    char_creation: bool = False,
) -> bytes:
    """Assemble the self-contained decoder appended to FONT-100.

    ``ui_text_ids`` (from :func:`load_fixed_ui_ids`) replaces the legacy
    cjk-mapping-v57 material/identity/class tables built into the asm.
    """
    for label, value in (
        ("staging offset", staging_offset),
        ("first slot offset", first_slot_offset),
        ("record size", record_bytes),
    ):
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"{label} must fit u16")
    if record_bytes == 0 or record_bytes % 2:
        raise ValueError("record size must be a non-zero even value")
    if not 1 <= bank_count <= 16:
        raise ValueError("bank count must be 1..16")
    id_limit = bank_count * 256
    extra_symbols: list[str] = []
    if backpack_ids is not None:
        if len(backpack_ids) != 2 or any(not 0 <= value < id_limit for value in backpack_ids):
            raise ValueError(f"backpack needs two IDs within the {bank_count} CJB1 banks")
        extra_symbols = ["--defsym", "fixed_backpack=1"]
        for index, value in enumerate(backpack_ids):
            extra_symbols += ["--defsym", f"backpack_id_{index}={value}"]
    if ability_ids is not None:
        if backpack_ids is None or len(ability_ids) != 12 or any(not 0 <= value < id_limit for value in ability_ids):
            raise ValueError(f"ability labels need backpack support and twelve IDs within {bank_count} banks")
        extra_symbols += ["--defsym", "fixed_abilities=1"]
        for index, value in enumerate(ability_ids):
            extra_symbols += ["--defsym", f"ability_id_{index}={value}"]
    if view_character:
        if ability_ids is None:
            raise ValueError("view-character layout requires ability labels")
        # v63 reflowed the six-ability grid from two rows of three columns
        # to three columns of two rows, so only one 12px row advance (not
        # two) needs to clear the identity text fixed at y=86.
        if not 0 <= view_y_origin <= 64:
            raise ValueError("view origin must leave room before identity row 86")
        extra_symbols += ["--defsym", "view_character=1", "--defsym", f"view_y_origin={view_y_origin}"]
    elif view_y_origin != 40:
        raise ValueError("view origin requires view-character support")
    if label_ids is not None:
        if ability_ids is None or len(label_ids) != 8 or any(not 0 <= value < id_limit for value in label_ids):
            raise ValueError(f"AC/PSI/view-HP/view-PSI labels need ability support and eight IDs within {bank_count} banks")
        extra_symbols += ["--defsym", "fixed_labels=1"]
        for index, value in enumerate(label_ids):
            name = ("ac_label_id_0", "ac_label_id_1", "psi_label_id_0", "psi_label_id_1",
                     "view_hp_label_id_0", "view_hp_label_id_1", "view_psi_label_id_0", "view_psi_label_id_1")[index]
            extra_symbols += ["--defsym", f"{name}={value}"]
    if materials:
        extra_symbols += ["--defsym", "fixed_materials=1"]
    if class_names:
        extra_symbols += ["--defsym", "fixed_class_names=1"]
    if menu_titles:
        extra_symbols += ["--defsym", "menu_titles=1"]
    if status_texts:
        extra_symbols += ["--defsym", "status_texts=1"]
    if text_draws:
        extra_symbols += ["--defsym", "text_draws=1"]
    if scroll_texts:
        if not text_draws:
            raise ValueError("scroll texts reuse the draw_text decoder")
        extra_symbols += ["--defsym", "scroll_texts=1"]
    if cursor_hotkeys:
        extra_symbols += ["--defsym", "cursor_hotkeys=1"]
    if smart_cursor:
        extra_symbols += ["--defsym", "smart_cursor=1"]
    if char_creation:
        if label_ids is None or not identity or not class_names:
            raise ValueError("character creation needs the fixed labels, identity and class names")
        extra_symbols += ["--defsym", "char_creation=1"]
    if identity:
        extra_symbols += ["--defsym", "fixed_identity=1"]
        if gender_position is not None:
            gy, gx = gender_position
            if not (0 <= gy <= 0xFFFF and 0 <= gx <= 0xFFFF):
                raise ValueError("gender position must fit u16")
            extra_symbols += ["--defsym", f"GENDER_Y={gy}", "--defsym", f"GENDER_X={gx}"]
        if alignment_position is not None:
            ay, ax_ = alignment_position
            if not (0 <= ay <= 0xFFFF and 0 <= ax_ <= 0xFFFF):
                raise ValueError("alignment position must fit u16")
            extra_symbols += ["--defsym", f"ALIGNMENT_Y={ay}", "--defsym", f"ALIGNMENT_X={ax_}"]
    else:
        if gender_position is not None:
            raise ValueError("gender position requires identity support")
        if alignment_position is not None:
            raise ValueError("alignment position requires identity support")
    if ui_text_ids is not None:
        for unit, values in ui_text_ids.items():
            if any(not 0 <= value < id_limit for value in values):
                raise ValueError(f"{unit} uses a CJK ID outside the {bank_count} banks")
        extra_symbols += ["--defsym", "generated_ui_text=1"]
    if class_row is not None:
        if not class_names or not all(0 <= value < 200 for value in class_row):
            raise ValueError("class row needs class-name support and two on-screen Y values")
        extra_symbols += ["--defsym", f"CLASS_ROW_FROM={class_row[0]}", "--defsym", f"CLASS_ROW_TO={class_row[1]}"]
    if stat_row_y is not None:
        if label_ids is None or not 0 <= stat_row_y < 200:
            raise ValueError("stat row needs the VIEW HP/PSI labels and an on-screen Y value")
        extra_symbols += ["--defsym", f"VIEW_STAT_ROW_Y={stat_row_y}"]
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        obj = directory / "name-cache.o"
        image = directory / "name-cache.exe"
        binary = directory / "name-cache.bin"
        if ui_text_ids is not None:
            (directory / "name_slot_ui_text.inc").write_text(
                name_slot_ui_text_include(ui_text_ids), encoding="ascii"
            )
        subprocess.run(
            [
                TOOLBIN / "as.exe",
                "--32",
                "-I",
                directory,
                "--defsym",
                f"staging_offset={staging_offset}",
                "--defsym",
                f"first_slot_offset={first_slot_offset}",
                "--defsym",
                f"cjk_record_bytes={record_bytes}",
                "--defsym",
                f"bank_count={bank_count}",
                *extra_symbols,
                "-o",
                obj,
                ASM,
            ],
            check=True,
        )
        linked = subprocess.run(
            [
                TOOLBIN / "ld.exe",
                "-m",
                "i386pe",
                "--section-start",
                f".text=0x{DECODER_OFFSET:X}",
                "-e",
                f"0x{DECODER_OFFSET:X}",
                "-o",
                image,
                obj,
            ],
            capture_output=True,
            text=True,
        )
        if linked.returncode:
            raise RuntimeError(linked.stderr.strip() or linked.stdout.strip())
        subprocess.run(
            [
                TOOLBIN / "objcopy.exe",
                "-O",
                "binary",
                "--only-section=.text",
                image,
                binary,
            ],
            check=True,
        )
        payload = binary.read_bytes()
    if DECODER_OFFSET + len(payload) > 0x10000:
        raise ValueError("FONT-local NAME cache exceeds the 16-bit allocation")
    return payload


def resident_font_trampoline(font_core_offset: int = FONT_CORE_PAYLOAD_OFFSET) -> bytes:
    """Preserve ES and transfer the far call into the FONT allocation."""
    if not 0 <= font_core_offset <= 0xFFFF:
        raise ValueError("FONT core offset must fit u16")
    payload = (
        b"\x06"  # push es; restored by the FONT-local decoder
        + bytes.fromhex("C4 1E 78 A3")  # les bx,[font_pointer]
        + b"\x81\xC3"
        + struct.pack("<H", font_core_offset)
        + b"\x06\x53\xCB"  # push es; push bx; retf
    )
    if len(payload) != 12:
        raise AssertionError("resident FONT trampoline is not exactly 12 bytes")
    return payload


def build_in_memory_v33_name_slot_executable(image: bytes) -> tuple[bytes, bytes]:
    """Refuse the rejected direct far-call plan.

    The four consumers live in dynamically relocated overlays. Adding their
    segment words to the main MZ relocation table corrupts memory during DOS
    startup; leaving them out would call the wrong runtime segment instead.
    A future plan must use an overlay-safe indirect call or existing relocation.
    """
    raise ValueError(
        "rejected NAME-slot executable plan: overlay consumer segment words "
        "must not be added to the main MZ relocation table"
    )


def build_in_memory_v37_name_slot_executable(image: bytes) -> tuple[bytes, bytes]:
    """Patch stable v33 with the pointer-free v42 NAME-slot design."""
    try:
        from .patch_dsun_scratch_cache import CODE_BASE, mz_relocation_file_offsets
    except ImportError:
        from patch_dsun_scratch_cache import CODE_BASE, mz_relocation_file_offsets

    verify_proven_consumer_sites(image)
    core = assemble_name_slot_cache()
    trampoline = resident_font_trampoline()
    trampoline_offset = CODE_BASE + RESIDENT_TRAMPOLINE_OFFSET
    if image[trampoline_offset : trampoline_offset + len(trampoline)] != bytes(len(trampoline)):
        raise ValueError("v37 resident FONT trampoline site is not all zero")

    for offset, (original, _) in ITEM_LINE_ADVANCE_PATCHES.items():
        if image[offset : offset + len(original)] != original:
            raise ValueError(f"v33 item line advance differs at 0x{offset:05X}")
    relocations_before = mz_relocation_file_offsets(image)
    result = bytearray(image)
    result[trampoline_offset : trampoline_offset + len(trampoline)] = trampoline
    for offset, (original, replacement) in ITEM_LINE_ADVANCE_PATCHES.items():
        result[offset : offset + len(original)] = replacement
    for offset in PROVEN_CONSUMER_OFFSETS:
        redirect = ds_relative_consumer_redirect_bytes(CONSUMER_CONTINUATION_IPS[offset])
        result[offset : offset + len(redirect)] = redirect

    final = bytes(result)
    if mz_relocation_file_offsets(final) != relocations_before:
        raise ValueError("v37 unexpectedly changed the main MZ relocation table")
    if final[trampoline_offset : trampoline_offset + len(trampoline)] != trampoline:
        raise ValueError("v37 resident FONT trampoline verification failed")
    for offset, (_, replacement) in ITEM_LINE_ADVANCE_PATCHES.items():
        if final[offset : offset + len(replacement)] != replacement:
            raise ValueError(f"v49 item line advance verification failed at 0x{offset:05X}")
    for offset in PROVEN_CONSUMER_OFFSETS:
        redirect = ds_relative_consumer_redirect_bytes(CONSUMER_CONTINUATION_IPS[offset])
        if final[offset : offset + len(redirect)] != redirect:
            raise ValueError(f"v42 redirect verification failed at 0x{offset:05X}")
    return final, core


def _rejected_build_in_memory_v33_name_slot_executable(
    image: bytes,
) -> tuple[bytes, bytes]:
    """Retained only as auditable evidence of the rejected v36 construction."""
    try:
        from .patch_dsun_scratch_cache import (
            CODE_BASE,
            mz_relocation_file_offsets,
            rewrite_mz_relocations,
        )
    except ImportError:
        from patch_dsun_scratch_cache import (
            CODE_BASE,
            mz_relocation_file_offsets,
            rewrite_mz_relocations,
        )

    verify_proven_consumer_sites(image)
    core = assemble_name_slot_cache()
    cave_offset = CODE_BASE + DECODER_OFFSET
    actual_cave = image[cave_offset : cave_offset + len(core)]
    if actual_cave != bytes(len(core)):
        raise ValueError(
            f"v33 decoder cave at 0x{cave_offset:05X} is not all zero"
        )
    existing_relocations = mz_relocation_file_offsets(image)
    added_relocations = set(consumer_segment_relocations())
    overlap = existing_relocations & added_relocations
    if overlap:
        raise ValueError(
            "planned NAME consumer relocation already exists: "
            + ", ".join(f"0x{offset:05X}" for offset in sorted(overlap))
        )

    result = bytearray(image)
    result[cave_offset : cave_offset + len(core)] = core
    height_offset = CODE_BASE + LEGACY_HEIGHT_HELPER
    if image[height_offset : height_offset + len(V33_HEIGHT_HELPER)] != V33_HEIGHT_HELPER:
        raise ValueError("v33 height helper differs from the reviewed source bytes")
    height_redirect = height_helper_redirect(core)
    result[height_offset : height_offset + len(height_redirect)] = height_redirect
    redirect = consumer_redirect_bytes()
    for offset in PROVEN_CONSUMER_OFFSETS:
        result[offset : offset + len(redirect)] = redirect
    rewrite_mz_relocations(result, set(), added_relocations)

    final = bytes(result)
    final_relocations = mz_relocation_file_offsets(final)
    if final_relocations != existing_relocations | added_relocations:
        raise ValueError("in-memory NAME consumer relocation verification failed")
    if final[cave_offset : cave_offset + len(core)] != core:
        raise ValueError("in-memory NAME cache core verification failed")
    if final[height_offset : height_offset + len(height_redirect)] != height_redirect:
        raise ValueError("in-memory height-helper redirect verification failed")
    for offset in PROVEN_CONSUMER_OFFSETS:
        if final[offset : offset + len(redirect)] != redirect:
            raise ValueError(f"in-memory redirect verification failed at 0x{offset:05X}")
    return final, core
