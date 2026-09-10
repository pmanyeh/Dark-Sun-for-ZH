#!/usr/bin/env python3
"""Build and verify overlay-safe redirects for proven NAME-1 UI consumers."""

from __future__ import annotations

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


def consumer_segment_relocations(
    offsets: Sequence[int] = PROVEN_CONSUMER_OFFSETS,
) -> frozenset[int]:
    """Return the segment words v36 wrongly treated as main-MZ relocations."""
    return frozenset(offset + 3 for offset in offsets)


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
) -> bytes:
    """Assemble the self-contained decoder appended to FONT-100."""
    for label, value in (
        ("staging offset", staging_offset),
        ("first slot offset", first_slot_offset),
        ("record size", record_bytes),
    ):
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"{label} must fit u16")
    if record_bytes == 0 or record_bytes % 2:
        raise ValueError("record size must be a non-zero even value")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        obj = directory / "name-cache.o"
        image = directory / "name-cache.exe"
        binary = directory / "name-cache.bin"
        subprocess.run(
            [
                TOOLBIN / "as.exe",
                "--32",
                "--defsym",
                f"staging_offset={staging_offset}",
                "--defsym",
                f"first_slot_offset={first_slot_offset}",
                "--defsym",
                f"cjk_record_bytes={record_bytes}",
                "--defsym",
                "bank_count=6",
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
