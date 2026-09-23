"""Fit four dialogue choices in WIND-3008 and page them in DSUN.EXE."""

from __future__ import annotations

import hashlib
from pathlib import Path

try:
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets, rewrite_mz_relocations
except ImportError:
    from patch_dsun_scratch_cache import mz_relocation_file_offsets, rewrite_mz_relocations


WIND_3008_SHA256 = "a8bfcc3de03485e17006e7066b979445cccca5568f7c1895dd5a07797e1c573f"
ROOT = Path(__file__).resolve().parent
# Unused padding inside the resident code segment. DS bytes after the
# initialized image are BSS and get cleared during startup.
CHOICE_RESTORE_CAVE = 0x33C60 + 0x9716
CHOICE_RESTORE_TEMPLATE = 0x33C60 + 0x9900
CHOICE_SET_TEXT = 0x2FDCA
CHOICE_SET_TEXT_PROLOGUE = bytes.fromhex("558BEC81ECEA00")
CODE_SEGMENT = 0x2E86
CHOICE_RESTORE_IP = 0x9716
CHOICE_IDS = range(0x081C, 0x0820)
REMOVED_CHOICE_ID = 0x0820
FIRST_CHOICE_Y = 13
PITCH = 11
HEIGHT_OFFSET = 0xC0

# File offsets in the original DSUN.EXE dialogue handler. These instructions
# govern the number of visible choices and the up/down page increment.
PAGE_SIZE_PATCHES = {
    0x7D8F8: (b"\x0A", b"\x04"),
    0x7D54D: (b"\x05", b"\x04"),
    0x7DA11: (b"\x05", b"\x04"),
    0x7DA24: (b"\x05", b"\x04"),
    0x7DC54: (b"\x05", b"\x04"),
    0x7DC6E: (b"\xFB\xFF", b"\xFC\xFF"),
    0x7DCC2: (b"\x05", b"\x04"),
    0x7DCC9: (b"\xFB\xFF", b"\xFC\xFF"),
    # Keep the next page at slot 4 even when fewer than four choices remain.
    0x7DCCF: (b"\x7D", b"\xEB"),
    0x7DCD7: (b"\xFB\xFF", b"\xFC\xFF"),
    0x7DCF5: (b"\xFB\xFF", b"\xFC\xFF"),
}


def _choice_restore_payloads() -> tuple[bytes, bytes]:
    hook = (ROOT / "dialogue_choice_top_rows_hook.bin").read_bytes()
    panel = (ROOT / "dialogue_choice_top_rows.bin").read_bytes()
    if not hook.endswith(b"\xEA\x01\x08\x1D\x2A"):
        raise ValueError("choice restore hook is missing its unrelocated return segment")
    if len(panel) != 608:
        raise ValueError("choice restore panel must be two 76-byte rows across four planes")
    if CHOICE_RESTORE_CAVE + len(hook) > CHOICE_RESTORE_TEMPLATE:
        raise ValueError("choice restore hook overlaps its panel template")
    return hook, panel


def patch_dialogue_choice_paging(executable: bytes) -> bytes:
    """Page four choices and repair the top two rows on the hidden page."""
    patched = bytearray(executable)
    for offset, (expected, replacement) in PAGE_SIZE_PATCHES.items():
        if patched[offset:offset + len(expected)] != expected:
            raise ValueError(f"dialogue page instruction mismatch at {offset:#x}")
        patched[offset:offset + len(expected)] = replacement

    hook, panel = _choice_restore_payloads()
    if patched[CHOICE_SET_TEXT:CHOICE_SET_TEXT + 7] != CHOICE_SET_TEXT_PROLOGUE:
        raise ValueError("choice text entry prologue does not match the verified function")
    for offset, payload in (
        (CHOICE_RESTORE_CAVE, hook),
        (CHOICE_RESTORE_TEMPLATE, panel),
    ):
        if any(patched[offset:offset + len(payload)]):
            raise ValueError(f"choice restore padding is not empty at {offset:#x}")
        patched[offset:offset + len(payload)] = payload

    call = b"\x9A" + CHOICE_RESTORE_IP.to_bytes(2, "little") + CODE_SEGMENT.to_bytes(2, "little") + b"\xEB\x00"
    patched[CHOICE_SET_TEXT:CHOICE_SET_TEXT + 7] = call
    return_site = CHOICE_RESTORE_CAVE + hook.rindex(b"\xEA\x01\x08\x1D\x2A") + 3
    rewrite_mz_relocations(
        patched,
        set(),
        {CHOICE_SET_TEXT + 3, return_site},
    )
    relocations = mz_relocation_file_offsets(bytes(patched))
    if not {CHOICE_SET_TEXT + 3, return_site} <= relocations:
        raise ValueError("choice restore far pointers were not added to the MZ relocation table")
    return bytes(patched)


def patch_dialogue_menu_wind(source: bytes, pitch: int) -> bytes:
    """Position four choice buttons and park the unused fifth button."""
    if pitch != PITCH:
        raise ValueError("four-choice dialogue layout requires an 11-pixel pitch")
    if hashlib.sha256(source).hexdigest() != WIND_3008_SHA256:
        raise ValueError("WIND-3008 source fingerprint does not match the verified layout")
    if int.from_bytes(source[HEIGHT_OFFSET:HEIGHT_OFFSET + 2], "little") != 58:
        raise ValueError("WIND-3008 source height is not 58 pixels")

    patched = bytearray(source)
    for index, button_id in enumerate(CHOICE_IDS):
        marker = b"BUTN" + button_id.to_bytes(4, "little")
        if source.count(marker) != 1:
            raise ValueError(f"WIND-3008 needs exactly one choice button {button_id:#06x}")
        offset = source.index(marker)
        if source[offset + 8:offset + 10] != b"\x03\x00":
            raise ValueError(f"WIND-3008 choice {button_id:#06x} has an unexpected X position")
        old_y = FIRST_CHOICE_Y + index * 8
        if int.from_bytes(source[offset + 10:offset + 12], "little") != old_y:
            raise ValueError(f"WIND-3008 choice {button_id:#06x} has an unexpected Y position")
        patched[offset + 10:offset + 12] = (FIRST_CHOICE_Y + index * pitch).to_bytes(2, "little")

    marker = b"BUTN" + REMOVED_CHOICE_ID.to_bytes(4, "little")
    if source.count(marker) != 1:
        raise ValueError("WIND-3008 fifth choice button is missing or duplicated")
    offset = source.index(marker)
    if offset != 0x19F or int.from_bytes(source[offset + 10:offset + 12], "little") != 45:
        raise ValueError("WIND-3008 fifth choice is not at the verified position")
    # Keep the serialized child intact. The dialogue code only populates the
    # first four buttons; the fifth is parked below the unchanged 58px window.
    patched[offset + 10:offset + 12] = (61).to_bytes(2, "little")
    return bytes(patched)
