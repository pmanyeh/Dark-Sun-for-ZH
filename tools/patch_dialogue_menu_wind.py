"""Fit four dialogue choices in WIND-3008 and page them in DSUN.EXE."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path

try:
    from .patch_dsun_scratch_cache import TOOLBIN, mz_relocation_file_offsets, rewrite_mz_relocations
except ImportError:
    from patch_dsun_scratch_cache import TOOLBIN, mz_relocation_file_offsets, rewrite_mz_relocations


WIND_3008_SHA256 = "a8bfcc3de03485e17006e7066b979445cccca5568f7c1895dd5a07797e1c573f"
ROOT = Path(__file__).resolve().parent
CHOICE_RESTORE_ASM = ROOT / "dialogue_choice_top_rows_hook.asm"
CHOICE_RESTORE_PANEL = ROOT / "dialogue_choice_top_rows.bin"
MZ_HEADER_BYTES = 0x5400
# Segment 147D holds one function (147D:0166..0219) that only uses cs:0164.
# The block 147D:000F..0163 before it is referenced by nothing. Zero runs
# elsewhere in the image are live: 2E86:53B6..55A6 is the timer ISR stack,
# and 2E86:D730 is inside the far data segment 3BF6.
CHOICE_RESTORE_SEGMENT = 0x147D
CHOICE_RESTORE_IP = 0x0010
CHOICE_RESTORE_LIMIT = 0x0164
CHOICE_RESTORE_CAVE = MZ_HEADER_BYTES + CHOICE_RESTORE_SEGMENT * 16 + CHOICE_RESTORE_IP
CHOICE_SET_TEXT = 0x2FDCA
CHOICE_SET_TEXT_PROLOGUE = bytes.fromhex("558BEC81ECEA00")
CHOICE_RETURN_JUMP = bytes.fromhex("EA01081D2A")
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


def _packed_panel() -> bytes:
    """Pack the 76-byte panel row of each plane as 2-bit values plus byte 0."""
    panel = CHOICE_RESTORE_PANEL.read_bytes()
    if len(panel) != 608:
        raise ValueError("choice restore panel must be two 76-byte rows across four planes")
    if panel[:304] != panel[304:]:
        raise ValueError("choice restore panel rows differ; the hook stamps one row twice")
    packed = bytearray()
    for plane in range(4):
        row = panel[plane * 76:(plane + 1) * 76]
        if any(not 0x18 <= value <= 0x1B for value in row[1:]):
            raise ValueError(f"choice restore panel plane {plane} has values outside 0x18..0x1B")
        values = [0] + [value - 0x18 for value in row[1:]]
        for index in range(0, 76, 4):
            packed.append(sum(values[index + bit] << (bit * 2) for bit in range(4)))
        packed.append(row[0])
    return bytes(packed)


def assemble_choice_restore() -> bytes:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        panel = _packed_panel()
        (directory / "panel.inc").write_text(
            "".join(
                "    .byte " + ", ".join(f"0x{value:02X}" for value in panel[index:index + 20]) + "\n"
                for index in range(0, len(panel), 20)
            ),
            encoding="ascii",
        )
        obj = directory / "hook.o"
        image = directory / "hook.exe"
        binary = directory / "hook.bin"
        subprocess.run(
            [TOOLBIN / "as.exe", "--32", "-I", directory, "-o", obj, CHOICE_RESTORE_ASM],
            check=True,
        )
        subprocess.run(
            [TOOLBIN / "ld.exe", "-m", "i386pe", "--section-start",
             f".text=0x{CHOICE_RESTORE_IP:X}", "-e", f"0x{CHOICE_RESTORE_IP:X}", "-o", image, obj],
            check=True,
            capture_output=True,
        )
        subprocess.run([TOOLBIN / "objcopy.exe", "-O", "binary", "--only-section=.text", image, binary], check=True)
        hook = binary.read_bytes()
    if hook.count(CHOICE_RETURN_JUMP) != 1:
        raise ValueError("choice restore hook must contain exactly one return jump")
    if CHOICE_RESTORE_IP + len(hook) > CHOICE_RESTORE_LIMIT:
        raise ValueError("choice restore hook reaches the live word at cs:0164")
    return hook


def patch_dialogue_choice_paging(executable: bytes) -> bytes:
    """Page four choices and repair the top two rows on the hidden page."""
    patched = bytearray(executable)
    for offset, (expected, replacement) in PAGE_SIZE_PATCHES.items():
        if patched[offset:offset + len(expected)] != expected:
            raise ValueError(f"dialogue page instruction mismatch at {offset:#x}")
        patched[offset:offset + len(expected)] = replacement

    hook = assemble_choice_restore()
    if patched[CHOICE_SET_TEXT:CHOICE_SET_TEXT + 7] != CHOICE_SET_TEXT_PROLOGUE:
        raise ValueError("choice text entry prologue does not match the verified function")
    cave_end = CHOICE_RESTORE_CAVE + len(hook)
    if any(patched[CHOICE_RESTORE_CAVE:cave_end]):
        raise ValueError(f"choice restore block is not empty at {CHOICE_RESTORE_CAVE:#x}")
    if any(CHOICE_RESTORE_CAVE <= site + 1 and site < cave_end
           for site in mz_relocation_file_offsets(bytes(patched))):
        raise ValueError("choice restore block overlaps an MZ relocation")
    patched[CHOICE_RESTORE_CAVE:cave_end] = hook

    call = (bytes([0x9A]) + CHOICE_RESTORE_IP.to_bytes(2, "little")
            + CHOICE_RESTORE_SEGMENT.to_bytes(2, "little") + bytes([0xEB, 0x00]))
    patched[CHOICE_SET_TEXT:CHOICE_SET_TEXT + 7] = call
    return_site = CHOICE_RESTORE_CAVE + hook.index(CHOICE_RETURN_JUMP) + 3
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
