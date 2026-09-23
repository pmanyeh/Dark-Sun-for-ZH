#!/usr/bin/env python3
"""Install the base-94 resolver plus resident single-bank scratch cache."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

try:
    from .patch_dsun_cjk16_probe import CODE_BASE, COMMON, triple_wrapper
except ImportError:
    from patch_dsun_cjk16_probe import CODE_BASE, COMMON, triple_wrapper

ROOT = Path(__file__).resolve().parents[1]
CACHE = 0x545A
CACHE_RUNTIME_LIMIT = 0x5534
STATE = 0x53B6
NAMES = 0x53F6
EBOX_OVERLAY_BASE = 0x31390
ITEM_TEXT_FILE_BASE = 0x30BA0
ITEM_FORMAT_LOOP = 0x02EB
ITEM_FORMAT_WRAPPER = 0x5414
ITEM_FORMAT_POST_HELPER = 0x51F1
ITEM_FORMAT_POST_HELPER_ALIAS = 0x82B1
EBOX_WIDTH_BODY = 0x0214
EBOX_LAYOUT_LOCALS = 0x0265
EBOX_LAYOUT_ADVANCE = 0x04A6
EBOX_ADVANCE_HELPER = 0x028A
EBOX_STORE_LINE_HEIGHT = 0x01CD
# GuiMenuLayout's vertical-menu line-pitch immediate (add ax, 2) inside the
# MENU control's own segment (0x2C450), file offset 0x2C716..0x2C718.  This
# is unrelated to EBOX_STORE_LINE_HEIGHT: the dialogue option list is drawn
# by a wholly separate MENU control that never consults the EBOX line table.
MENU_LAYOUT_LINE_GAP_FILE_OFFSET = 0x2C716
CJK_HEIGHT_HELPER = 0x53D6
GLYPH_HEIGHT_LOAD = 0x0704
# The two game-side EBOX dispatchers negate SI=5 immediately before passing
# the next-page delta to the shared scroll routine.  Keep SI itself untouched:
# it also participates in the original control feedback path.  These are file
# offsets, not offsets in the EBOX overlay above.
EBOX_NEXT_PAGE_DELTA_FILE_OFFSETS = (0x7CDBC, 0x7DBC5)
# GPL/MAS chunks are loaded into one pool (3781:0255, size 3781:0313) that
# the loader fills with chunk bytes plus a trailing 0x31 exit; a chunk
# only loads while size + 1 < pool size. The overlay startup code sets the
# pool with `push dword 10000; push 200; call far <init>` (file offset
# 0x6A692). Translated GPL-146 grew to 10,706 bytes, never loaded, and the
# Trustee's dialogue failed with BAD GPL EXIT; the original game's largest
# chunk (GPL-2) is 9,792. Runtime read of 3781:0313 confirmed 0x2710.
GPL_POOL_SIZE_FILE_OFFSET = 0x6A694
GPL_POOL_ORIGINAL_BYTES = 10000
GPL_POOL_BYTES = 0x3000
# Largest chunk that still loads: size + 1 must stay below the pool size.
GPL_MAX_CHUNK_BYTES = GPL_POOL_BYTES - 2
ASM = ROOT / "tools/cjk_scratch_cache.asm"
TOOLBIN = ROOT / ".tools/w64devkit/bin"

# Beyond 8 banks the inline table at NAMES no longer fits before COMMON.
# Segment 147D is dead padding verified by static analysis (no far pointer
# or CS-relative reference anywhere in the module touches 147D:000F..0163
# except the one unrelated function starting at 147D:0166 -- see
# tools/patch_dialogue_menu_wind.py's CHOICE_RESTORE_CAVE, which occupies
# 147D:0010..00FB for a different, independent repair). The cache asm's
# "bank_names_cave_*" .equ constants must match these exactly.
MZ_HEADER_BYTES = 0x5400
BANK_NAMES_CAVE_SEGMENT = 0x147D
BANK_NAMES_CAVE_TABLE = 0x0110
# 147D:015C..0163 holds the translated INTRODUCE prefix (see
# patch_introduce_prefix), so the name table may grow to 14 banks.
BANK_NAMES_CAVE_LIMIT = 0x015C
BANK_NAMES_CAVE_FILE_OFFSET = MZ_HEADER_BYTES + BANK_NAMES_CAVE_SEGMENT * 16 + BANK_NAMES_CAVE_TABLE
# The 20 bytes between the choice-restore hook (147D:0010..00FB) and the bank
# name table hold the EBOX CJK line-break routine; see ebox_cjk_break_routine.
EBOX_BREAK_CAVE_IP = 0x00FC
EBOX_BREAK_CAVE_FILE_OFFSET = MZ_HEADER_BYTES + BANK_NAMES_CAVE_SEGMENT * 16 + EBOX_BREAK_CAVE_IP
# File offset of the segment word in the helper's `call far 147D:00FC`.
EBOX_BREAK_CALL_RELOCATION = EBOX_OVERLAY_BASE + EBOX_ADVANCE_HELPER + 3


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mz_relocation_file_offsets(image: bytes) -> set[int]:
    """Return file offsets of every 16-bit word adjusted by the DOS loader."""
    if image[:2] != b"MZ" or len(image) < 0x1C:
        raise ValueError("DSUN executable is not a valid MZ image")
    count = struct.unpack_from("<H", image, 0x06)[0]
    header_bytes = struct.unpack_from("<H", image, 0x08)[0] * 16
    table = struct.unpack_from("<H", image, 0x18)[0]
    if table + count * 4 > header_bytes or header_bytes > len(image):
        raise ValueError("DSUN executable has an invalid MZ relocation table")
    result = set()
    for index in range(count):
        offset, segment = struct.unpack_from("<HH", image, table + index * 4)
        result.add(header_bytes + segment * 16 + offset)
    return result


def rewrite_mz_relocations(
    image: bytearray, remove_file_offsets: set[int], add_file_offsets: set[int]
) -> None:
    """Replace selected MZ relocation words without moving the load image."""
    count = struct.unpack_from("<H", image, 0x06)[0]
    header_bytes = struct.unpack_from("<H", image, 0x08)[0] * 16
    table = struct.unpack_from("<H", image, 0x18)[0]
    entries: list[tuple[int, int]] = []
    removed: set[int] = set()
    for index in range(count):
        offset, segment = struct.unpack_from("<HH", image, table + index * 4)
        file_offset = header_bytes + segment * 16 + offset
        if file_offset in remove_file_offsets:
            removed.add(file_offset)
        else:
            entries.append((offset, segment))
    if removed != remove_file_offsets:
        missing = sorted(remove_file_offsets - removed)
        raise ValueError(
            "missing MZ relocation(s) to replace: "
            + ", ".join(f"0x{item:05X}" for item in missing)
        )
    existing = {
        header_bytes + segment * 16 + offset for offset, segment in entries
    }
    for file_offset in sorted(add_file_offsets - existing):
        linear = file_offset - header_bytes
        if not 0 <= linear <= 0xFFFFF:
            raise ValueError(f"MZ relocation is outside the load image: 0x{file_offset:05X}")
        entries.append((linear & 0xF, linear >> 4))
    end = table + len(entries) * 4
    if end > header_bytes:
        raise ValueError("MZ header has no room for the added relocation entries")
    struct.pack_into("<H", image, 0x06, len(entries))
    for index, (offset, segment) in enumerate(entries):
        struct.pack_into("<HH", image, table + index * 4, offset, segment)


def assemble_cache(scratch_offset: int = 0x3640, record_bytes: int = 242, bank_count: int = 4) -> bytes:
    if not 0 <= scratch_offset <= 0xFFFF:
        raise ValueError("scratch offset must fit u16")
    if not 1 <= record_bytes <= 0xFFFF:
        raise ValueError("record size must fit a non-zero u16")
    if not 1 <= bank_count <= 16:
        raise ValueError("bank count must be 1..16")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        obj = directory / "cache.o"
        image = directory / "cache.exe"
        binary = directory / "cache.bin"
        subprocess.run(
            [
                TOOLBIN / "as.exe",
                "--32",
                "--defsym",
                f"scratch_offset={scratch_offset}",
                "--defsym",
                f"cjk_record_bytes={record_bytes}",
                "--defsym",
                f"bank_count={bank_count}",
                "-o",
                obj,
                ASM,
            ],
            check=True,
        )
        subprocess.run(
            [TOOLBIN / "ld.exe", "-m", "i386pe", "--section-start", f".text=0x{CACHE:X}", "-e", f"0x{CACHE:X}", "-o", image, obj],
            check=True,
            capture_output=True,
        )
        subprocess.run([TOOLBIN / "objcopy.exe", "-O", "binary", "--only-section=.text", image, binary], check=True)
        return binary.read_bytes()


def resolver() -> bytes:
    code = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str]] = []

    def emit(value: str) -> None:
        code.extend(bytes.fromhex(value))

    def label(name: str) -> None:
        labels[name] = len(code)

    def jcc(opcode: int, target: str) -> None:
        fixups.append((len(code), target))
        code.extend((opcode, 0))

    emit("26 8A 07 3C 5E")
    jcc(0x75, "ordinary")
    emit("26 8A 47 01 2C 21 3C 5D")
    jcc(0x77, "ordinary")
    emit("30 E4 B2 5E F6 E2 26 8A 57 02 80 EA 21 80 FA 5D")
    jcc(0x77, "ordinary")
    emit("30 F6 03 C2 3D A3 16")
    jcc(0x74, "reserved")
    call_position = COMMON + len(code)
    displacement = (CACHE - (call_position + 3)) & 0xFFFF
    code.extend(b"\xE8" + struct.pack("<H", displacement) + b"\xC3")
    label("reserved")
    emit("B8 3F 01 C3")
    label("ordinary")
    emit("26 8A 07 30 E4 C3")
    for position, target in fixups:
        delta = labels[target] - position - 2
        if not -128 <= delta <= 127:
            raise ValueError("resolver short branch is out of range")
        code[position + 1] = delta & 0xFF
    return bytes(code)


def ebox_cjk_width_body() -> bytes:
    """Make EBOX measure one printable triple as one 10-pixel glyph.

    The function prologue through 0x0213 is deliberately left intact because
    its far stack-check call owns an MZ relocation word.  This replacement is
    exactly the original 0x0214..0x0239 body and contains no relocation sites.
    """
    code = bytes.fromhex(
        "8A 46 06 "                # mov al,[bp+06]
        "3C 5E 74 1A "             # printable triple lead -> fixed width
        "30 E4 D1 E0 "             # ordinary unsigned byte index * 2
        "C4 1E 78 A3 03 D8 "       # FONT base + offset-table index
        "26 8B 97 08 01 "          # glyph record relative offset
        "C4 1E 78 A3 03 DA "       # reload FONT base and add record offset
        "26 8B 07 C9 CB "          # return record width
        "B8 0A 00 C9 CB"           # CJK advance = 10
    )
    expected = 0x023A - EBOX_WIDTH_BODY
    if len(code) != expected:
        raise ValueError(f"EBOX width body is {len(code)} bytes, expected {expected}")
    return code


def ebox_layout_locals_and_helper() -> bytes:
    """Compress EBOX locals and embed a triple-aware byte-index advance.

    The preceding 0x025A..0x0264 stack check is not touched: its segment word
    is relocated by the DOS loader.  The compact initialization plus helper
    occupies exactly the original initialization range.
    """
    initialization = bytes.fromhex(
        "31 C0 "
        "89 46 EA 89 46 E8 "       # zero
        "48 89 46 E6 89 46 E4 "    # -1 sentinels
        "40 "
        "89 46 E2 89 46 E0 89 46 DE 89 46 DC 89 46 F8 "
        "40 89 46 FA "             # one
        "EB 0D"                    # normal entry skips embedded helper
    )
    helper = (
        bytes((0x9A,))                           # call far 147D:00FC
        + struct.pack("<HH", EBOX_BREAK_CAVE_IP, BANK_NAMES_CAVE_SEGMENT)
        + bytes.fromhex(
            "46 3B 76 F4 C3 "      # common increment, loop cmp, return
            "90 90 90"
        )
    )
    if EBOX_LAYOUT_LOCALS + len(initialization) != EBOX_ADVANCE_HELPER:
        raise ValueError("EBOX initialization does not meet embedded helper")
    payload = initialization + helper
    expected = 0x0297 - EBOX_LAYOUT_LOCALS
    if len(payload) != expected:
        raise ValueError(f"EBOX local/helper block is {len(payload)} bytes, expected {expected}")
    return payload


def ebox_cjk_break_routine() -> bytes:
    """Let EBOX wrap after any CJK glyph instead of only at spaces.

    The layout loop treats a run without spaces as one word: [bp-1C] is the
    current word's start (-1 = none), [bp-24] says a word is open, and
    [bp-1A] != -1 says the line already holds a finished word. On overflow
    it carries the open word to the next line, or breaks at the overflowing
    byte when there is no open word. A space-free Chinese sentence was one
    word, so every translated print fragment jumped to a fresh line.

    After each '^' triple this closes the word and marks the line breakable,
    so an overflowing glyph breaks right before itself and an ASCII word
    that follows CJK text is still carried whole. It also advances SI past
    the triple's two trailing bytes; the caller adds the common increment.
    """
    code = bytes.fromhex(
        "80 7E F6 5E "             # cmp byte [bp-0A],'^'
        "75 0D "                   # not a triple -> return
        "89 76 E6 "                # mov [bp-1A],si: line has a break point
        "83 4E E4 FF "             # or word [bp-1C],-1: no open word start
        "83 66 DC 00 "             # and word [bp-24],0: word closed
        "46 46 "                   # skip the triple's two trailing bytes
        "CB"                       # retf
    )
    if len(code) != BANK_NAMES_CAVE_TABLE - EBOX_BREAK_CAVE_IP:
        raise ValueError(f"EBOX break routine is {len(code)} bytes, expected 20")
    return code


# The INTRODUCE menu option ("I'm <name>") is built in DSUN.EXE, not GPL:
#   0xD088  push 377E / push 0000 / push ds / push 4285 / call far strcpy
#   0xD0A4  ... strcat(DS:4285, active character name); return DS:4285
# 377E:0000 holds "I'm \0" but 377E:0019.. are live variables, so the prefix
# cannot grow in place. The strcpy source is repointed instead; its segment
# word at 0xD089 already carries an MZ relocation. The next variable after
# DS:4285 is DS:42C8, so the 67-byte buffer has room for a longer prefix.
INTRODUCE_STRCPY_SOURCE = 0xD088
INTRODUCE_STRCPY_ORIGINAL = bytes.fromhex("68 7E 37 68 00 00")
INTRODUCE_ORIGINAL_TEXT_FILE_OFFSET = MZ_HEADER_BYTES + 0x377E * 16
INTRODUCE_PREFIX_CAVE_IP = BANK_NAMES_CAVE_LIMIT
INTRODUCE_PREFIX_CAVE_LIMIT = 0x0164
INTRODUCE_PREFIX_FILE_OFFSET = (
    MZ_HEADER_BYTES + BANK_NAMES_CAVE_SEGMENT * 16 + INTRODUCE_PREFIX_CAVE_IP
)


def patch_introduce_prefix(image: bytes, encoded_prefix: bytes) -> bytes:
    """Point the INTRODUCE option's "I'm " prefix at a translated string."""
    text = encoded_prefix + b"\0"
    if len(text) > INTRODUCE_PREFIX_CAVE_LIMIT - INTRODUCE_PREFIX_CAVE_IP:
        raise ValueError(f"INTRODUCE prefix is {len(text)} bytes, beyond the 8-byte cave")
    if image[INTRODUCE_ORIGINAL_TEXT_FILE_OFFSET:INTRODUCE_ORIGINAL_TEXT_FILE_OFFSET + 5] != b"I'm \0":
        raise ValueError("DSUN.EXE does not hold the original INTRODUCE prefix at 377E:0000")
    site = INTRODUCE_STRCPY_SOURCE
    if image[site:site + 6] != INTRODUCE_STRCPY_ORIGINAL:
        raise ValueError(f"unexpected INTRODUCE strcpy source at 0x{site:05X}")
    if site + 1 not in mz_relocation_file_offsets(image):
        raise ValueError("INTRODUCE strcpy source segment is not relocated")
    cave = INTRODUCE_PREFIX_FILE_OFFSET
    if any(image[cave:cave + len(text)]):
        raise ValueError(f"INTRODUCE prefix cave is not empty at 0x{cave:05X}")
    patched = bytearray(image)
    patched[cave:cave + len(text)] = text
    patched[site:site + 6] = (
        bytes((0x68,)) + struct.pack("<H", BANK_NAMES_CAVE_SEGMENT)
        + bytes((0x68,)) + struct.pack("<H", INTRODUCE_PREFIX_CAVE_IP)
    )
    return bytes(patched)


def ebox_layout_advance_call() -> bytes:
    displacement = (EBOX_ADVANCE_HELPER - (EBOX_LAYOUT_ADVANCE + 3)) & 0xFFFF
    return b"\xE8" + struct.pack("<H", displacement) + b"\x90"


def ebox_store_line_height(line_gap: int) -> bytes:
    """Add leading to the line table so layout, clipping, and drawing agree."""
    if not 1 <= line_gap <= 2:
        raise ValueError("EBOX layout line gap must be 1 or 2 pixels")
    payload = (
        b"\x41" * line_gap                    # inc cx: stored line height
        + bytes.fromhex("6B C2 04")             # imul ax,dx,4 (compact address calc)
        + bytes.fromhex("03 D8 26 89 4F 04")   # add bx,ax; mov es:[bx+4],cx
    )
    return payload + b"\x90" * (11 - len(payload))


def ebox_page_step(line_gap: int) -> int:
    """Keep the legacy five-line page action in sync with added leading.

    This is an explicit compatibility profile for the existing EBOX geometry.
    It is intentionally separate from glyph height: line_gap changes the
    number of line records that fit in the viewport, not the bitmap cell.
    """
    if not 0 <= line_gap <= 2:
        raise ValueError("EBOX layout line gap must be 0, 1, or 2 pixels")
    return 5 - line_gap


def menu_layout_line_gap(line_gap: int) -> bytes:
    """Widen GuiMenuLayout's per-item vertical pitch beyond font_height + 2.

    The MENU control (dialogue option list) advances its Y cursor by exactly
    font_height + 2 for every item, hardcoded as `add ax, 2` at file offset
    0x2C716. That headroom is tuned for 6-7px-tall English glyphs; CJK glyphs
    are 10-12px tall (with shadow), so the stock +2 leaves 0px of leading and
    adjacent option lines visually merge. This only changes the immediate
    operand, so it is a same-size, same-opcode overwrite with no relocation
    or code-space implications (unlike the EBOX line-gap patch).
    """
    if not 2 <= line_gap <= 9:
        raise ValueError("menu layout line gap must be 2..9 pixels")
    return bytes((0x05, line_gap, 0x00))


def cjk_height_helper(cjk_draw_height: int) -> bytes:
    """Return 10 for marker byte 0x7F so its shared draw/clip path stays aligned."""
    if cjk_draw_height not in (9, 10):
        raise ValueError("CJK draw height must be 9 or 10")
    code = bytearray(bytes.fromhex("B8 09 00 80 7E 06 7F 75 01"))
    code += b"\x40" if cjk_draw_height == 10 else b"\x90"
    code += b"\xC3"
    return bytes(code)


def glyph_height_call() -> bytes:
    displacement = (CJK_HEIGHT_HELPER - (GLYPH_HEIGHT_LOAD + 3)) & 0xFFFF
    return b"\xE8" + struct.pack("<H", displacement) + bytes.fromhex("89 46 E8") + b"\x90" * 5


def item_format_wrapper() -> bytes:
    """Resolve one `%Fs` byte and return AX unchanged to the caller.

    AH is the ASCII/CJK source-length flag.  The caller keeps the complete AX
    on its own stack while FONT receives a second, AH-cleared copy.  This avoids
    v34's unsafe use of a formatter local and keeps ES:BX unchanged for FONT.
    """
    displacement = (COMMON - (ITEM_FORMAT_WRAPPER + 3)) & 0xFFFF
    return b"\xE8" + struct.pack("<H", displacement) + b"\xCB"


def item_format_post_helper() -> bytes:
    """Advance a `%Fs` source after FONT has consumed the current glyph.

    The formatter segment aliases resident offset 51F1 at 82B1.  This helper
    occupies the start of the original executable's 433-byte zero-filled gap,
    immediately before the existing resident CJK wrappers.
    """
    return bytes.fromhex(
        "03 F7 "                  # extend dirty rectangle after FONT
        "8A C4 D0 E0 FE C0 30 E4 " # returned AH flag 0/1 -> AX length 1/3
        "01 46 F2 "               # advance full 16-bit far-string offset
        "C4 5E F2 26 80 3F 00 "   # reload source; end of string?
        "C3"
    )


def item_format_loop() -> bytes:
    """Render a far string with balanced stack storage across FONT."""
    helper_displacement = (
        ITEM_FORMAT_POST_HELPER_ALIAS - (ITEM_FORMAT_LOOP + 19)
    ) & 0xFFFF
    payload = bytes.fromhex(
        "9A 14 54 86 2E "          # call 2E86:5414 (runtime 36AA:5414)
        "50 30 E4 50 "             # save AX flag; push clean glyph argument
        "9A C1 59 80 09 "          # call FONT renderer (runtime 11A4:59C1)
        "59 58 E8 "                # discard glyph; restore flag; post helper
    )
    payload += struct.pack("<H", helper_displacement)
    payload += bytes.fromhex(
        "75 EB EB 6A "             # loop, or join the outer formatter
        "90 90 90 90"
    )
    if len(payload) != 0x0306 - ITEM_FORMAT_LOOP:
        raise ValueError("item format loop replacement has the wrong size")
    return payload


def patches(
    cache: bytes,
    line_gap: int = 0,
    cjk_draw_height: int = 9,
    bank_count: int = 4,
    experimental_item_text_fix: bool = False,
    menu_line_gap: int = 2,
) -> dict[int, tuple[bytes, bytes]]:
    if not 1 <= bank_count <= 16:
        raise ValueError("bank count must be 1..16")
    menu_gap_patch = menu_layout_line_gap(menu_line_gap)
    resolve = resolver()
    state = bytes.fromhex("FF 00 FF FF 00 00 00 00 00 00 00 00 00 00")
    # DOS does not require a filename extension; dropping ".BIN" keeps each
    # entry to 3 bytes ("C{n}\0") for banks 0..9. Past 8 banks the table no
    # longer fits between NAMES and the resolver stub at COMMON, so it moves
    # to the verified-dead cave in segment 147D instead (see
    # BANK_NAMES_CAVE_FILE_OFFSET above); the cache asm's .if bank_count > 8
    # branch loads that segment before reading the table.
    filenames = tuple(f"C{bank}\0".encode("ascii") for bank in range(bank_count))
    table_bytes = bank_count * 2
    if bank_count <= 8:
        offset = NAMES + table_bytes
        name_offsets = []
        for filename in filenames:
            name_offsets.append(offset)
            offset += len(filename)
        names = struct.pack(f"<{bank_count}H", *name_offsets) + b"".join(filenames)
        names_limit = ITEM_FORMAT_WRAPPER if experimental_item_text_fix else COMMON
        if NAMES + len(names) > min(CACHE, names_limit):
            raise ValueError(
                f"bank name table for {bank_count} banks ends at 0x{NAMES + len(names):04X}, "
                f"beyond the resolver data limit 0x{names_limit:04X}"
            )
        name_table_patch = {CODE_BASE + NAMES: (bytes(len(names)), names)}
    else:
        offset = BANK_NAMES_CAVE_TABLE + table_bytes
        name_offsets = []
        for filename in filenames:
            name_offsets.append(offset)
            offset += len(filename)
        names = struct.pack(f"<{bank_count}H", *name_offsets) + b"".join(filenames)
        if BANK_NAMES_CAVE_TABLE + len(names) > BANK_NAMES_CAVE_LIMIT:
            raise ValueError(
                f"bank name table for {bank_count} banks ends at 0x{BANK_NAMES_CAVE_TABLE + len(names):04X} "
                f"in segment 0x{BANK_NAMES_CAVE_SEGMENT:04X}, beyond the verified-dead limit "
                f"0x{BANK_NAMES_CAVE_LIMIT:04X}"
            )
        name_table_patch = {BANK_NAMES_CAVE_FILE_OFFSET: (bytes(len(names)), names)}
    result = {
        CODE_BASE + 0x094A: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 59 4A")),
        CODE_BASE + 0x07F8: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 CB 4B")),
        CODE_BASE + 0x09A2: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 41 4A")),
        CODE_BASE + 0x53A6: (bytes(16), triple_wrapper(0x53A6, 0xFA)),
        CODE_BASE + 0x53C6: (bytes(16), triple_wrapper(0x53C6, 0x06)),
        CODE_BASE + 0x53E6: (bytes(16), triple_wrapper(0x53E6, 0xF6)),
        CODE_BASE + STATE: (bytes(len(state)), state),
        **name_table_patch,
        CODE_BASE + COMMON: (bytes(len(resolve)), resolve),
        CODE_BASE + CACHE: (bytes(len(cache)), cache),
        EBOX_OVERLAY_BASE + EBOX_WIDTH_BODY: (
            bytes.fromhex(
                "8A 46 06 98 D1 E0 C4 1E 78 A3 03 D8 A1 7A A3 8B 16 78 A3 "
                "26 03 97 08 01 89 46 FE 89 56 FC C4 5E FC 26 8B 07 C9 CB"
            ),
            ebox_cjk_width_body(),
        ),
        EBOX_OVERLAY_BASE + EBOX_LAYOUT_LOCALS: (
            bytes.fromhex(
                "C7 46 EA 00 00 C7 46 E8 00 00 C7 46 E6 FF FF C7 46 E4 FF FF "
                "C7 46 E2 00 00 C7 46 E0 00 00 C7 46 DE 00 00 C7 46 DC 00 00 "
                "C7 46 F8 00 00 C7 46 FA 01 00"
            ),
            ebox_layout_locals_and_helper(),
        ),
        EBOX_OVERLAY_BASE + EBOX_LAYOUT_ADVANCE: (
            bytes.fromhex("46 3B 76 F4"),
            ebox_layout_advance_call(),
        ),
        EBOX_BREAK_CAVE_FILE_OFFSET: (bytes(20), ebox_cjk_break_routine()),
        GPL_POOL_SIZE_FILE_OFFSET: (
            struct.pack("<I", GPL_POOL_ORIGINAL_BYTES),
            struct.pack("<I", GPL_POOL_BYTES),
        ),
    }
    if experimental_item_text_fix:
        result[CODE_BASE + ITEM_FORMAT_WRAPPER] = (
            bytes(len(item_format_wrapper())), item_format_wrapper()
        )
        result[CODE_BASE + ITEM_FORMAT_POST_HELPER] = (
            bytes(len(item_format_post_helper())), item_format_post_helper()
        )
        result[ITEM_TEXT_FILE_BASE + ITEM_FORMAT_LOOP] = (
            bytes.fromhex(
                "26 8A 07 98 50 9A C1 59 80 09 59 03 F7 FF 46 F2 "
                "C4 5E F2 26 80 3F 00 75 E4 EB 66"
            ),
            item_format_loop(),
        )
    if cjk_draw_height != 9:
        result[CODE_BASE + CJK_HEIGHT_HELPER] = (
            bytes(len(cjk_height_helper(cjk_draw_height))),
            cjk_height_helper(cjk_draw_height),
        )
        result[CODE_BASE + GLYPH_HEIGHT_LOAD] = (
            bytes.fromhex("C4 1E 78 A3 26 8B 47 02 89 46 E8"),
            glyph_height_call(),
        )
    if line_gap:
        result[EBOX_OVERLAY_BASE + EBOX_STORE_LINE_HEIGHT] = (
            bytes.fromhex("8B C2 C1 E0 02 03 D8 26 89 4F 04"),
            ebox_store_line_height(line_gap),
        )
        step = ebox_page_step(line_gap)
        # Original: mov ax,si; neg ax; push ax.  A signed imm8 push expresses
        # the layout-specific negative delta without altering SI=5.
        next_delta = bytes((0x6A, (-step) & 0xFF)) + b"\x90\x90\x90"
        for offset in EBOX_NEXT_PAGE_DELTA_FILE_OFFSETS:
            result[offset] = (bytes.fromhex("8B C6 F7 D8 50"), next_delta)
    if menu_line_gap != 2:
        result[MENU_LAYOUT_LINE_GAP_FILE_OFFSET] = (
            bytes.fromhex("05 02 00"),
            menu_gap_patch,
        )
    return result


def patch_executable(
    source: bytes,
    scratch_offset: int = 0x3640,
    record_bytes: int = 242,
    line_gap: int = 0,
    cjk_draw_height: int = 9,
    bank_count: int = 4,
    experimental_item_text_fix: bool = False,
    menu_line_gap: int = 2,
) -> tuple[bytes, bytes]:
    """Return a verified scratch-cache executable image and assembled cache."""
    data = bytearray(source)
    cache = assemble_cache(scratch_offset, record_bytes, bank_count)
    if CACHE + len(cache) > CACHE_RUNTIME_LIMIT:
        raise ValueError(
            f"resident cache ends at 0x{CACHE + len(cache):04X}, "
            f"beyond runtime-safe boundary 0x{CACHE_RUNTIME_LIMIT:04X}"
        )
    planned = patches(
        cache,
        line_gap,
        cjk_draw_height,
        bank_count,
        experimental_item_text_fix,
        menu_line_gap,
    )
    relocations = mz_relocation_file_offsets(source)
    removed_relocations = (
        {ITEM_TEXT_FILE_BASE + 0x02F3} if experimental_item_text_fix else set()
    )
    added_relocations = set(
        {ITEM_TEXT_FILE_BASE + 0x02EE, ITEM_TEXT_FILE_BASE + 0x02F7}
        if experimental_item_text_fix else set()
    )
    # The EBOX advance helper's far call into segment 147D.
    added_relocations.add(EBOX_BREAK_CALL_RELOCATION)
    if bank_count > 8:
        # The cache's cache_open routine pushes this immediate and pops it
        # into DS before reading the bank-name table out of segment 147D;
        # the loader must relocate it exactly like every other far
        # reference in this module.
        marker = bytes((0x68,)) + BANK_NAMES_CAVE_SEGMENT.to_bytes(2, "little")
        if cache.count(marker) != 1:
            raise ValueError("bank-names cave segment immediate not found exactly once in cache")
        bank_names_relocation = CODE_BASE + CACHE + cache.index(marker) + 1
        added_relocations.add(bank_names_relocation)
    if experimental_item_text_fix and not removed_relocations <= relocations:
        raise ValueError("item format loop's original far-call relocation is missing")
    final_relocations = (relocations - removed_relocations) | added_relocations
    relocated_bytes = final_relocations | {offset + 1 for offset in final_relocations}
    allowed_relocated_bytes = added_relocations | {offset + 1 for offset in added_relocations}
    for offset, (_, replacement) in planned.items():
        overlap = sorted(
            (set(range(offset, offset + len(replacement))) & relocated_bytes)
            - allowed_relocated_bytes
        )
        if overlap:
            raise ValueError(
                f"patch at 0x{offset:05X} overlaps MZ relocation word(s): "
                + ", ".join(f"0x{item:05X}" for item in overlap)
            )
    for offset, (expected, replacement) in planned.items():
        actual = bytes(data[offset : offset + len(expected)])
        if actual != expected:
            raise ValueError(f"unexpected bytes at 0x{offset:05X}: {actual.hex()}")
        data[offset : offset + len(replacement)] = replacement
    if removed_relocations or added_relocations:
        rewrite_mz_relocations(data, removed_relocations, added_relocations)
    result = bytes(data)
    for offset, (_, replacement) in planned.items():
        if result[offset : offset + len(replacement)] != replacement:
            raise ValueError(f"patched bytes failed verification at 0x{offset:05X}")
    final = mz_relocation_file_offsets(result)
    if bank_count > 8 and bank_names_relocation not in final:
        raise ValueError("bank-names cave segment word was not added to the MZ relocation table")
    if EBOX_BREAK_CALL_RELOCATION not in final:
        raise ValueError("EBOX break call segment word was not added to the MZ relocation table")
    return result, cache


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch-offset", type=lambda value: int(value, 0), default=0x3640)
    parser.add_argument("--record-bytes", type=lambda value: int(value, 0), default=242)
    parser.add_argument("--line-gap", type=int, default=0)
    parser.add_argument("--menu-line-gap", type=int, default=2)
    args = parser.parse_args()
    data, cache = patch_executable(
        args.exe.read_bytes(),
        args.scratch_offset,
        args.record_bytes,
        args.line_gap,
        menu_line_gap=args.menu_line_gap,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"resolver_bytes={len(resolver())}")
    print(f"cache_offset=0x{CACHE:04X}")
    print(f"cache_bytes={len(cache)}")
    print(f"scratch_offset=0x{args.scratch_offset:04X}")
    print(f"record_bytes={args.record_bytes}")
    print(f"sha256={sha256(data)}")
    print(args.output)


if __name__ == "__main__":
    main()
