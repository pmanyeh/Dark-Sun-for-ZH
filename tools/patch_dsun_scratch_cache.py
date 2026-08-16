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
EBOX_WIDTH_BODY = 0x0214
EBOX_LAYOUT_LOCALS = 0x0265
EBOX_LAYOUT_ADVANCE = 0x04A6
EBOX_ADVANCE_HELPER = 0x028A
EBOX_STORE_LINE_HEIGHT = 0x01CD
CJK_HEIGHT_HELPER = 0x53D6
GLYPH_HEIGHT_LOAD = 0x0704
# The two game-side EBOX dispatchers negate SI=5 immediately before passing
# the next-page delta to the shared scroll routine.  Keep SI itself untouched:
# it also participates in the original control feedback path.  These are file
# offsets, not offsets in the EBOX overlay above.
EBOX_NEXT_PAGE_DELTA_FILE_OFFSETS = (0x7CDBC, 0x7DBC5)
ASM = ROOT / "tools/cjk_scratch_cache.asm"
TOOLBIN = ROOT / ".tools/w64devkit/bin"


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


def assemble_cache(scratch_offset: int = 0x3640, record_bytes: int = 242, bank_count: int = 4) -> bytes:
    if not 0 <= scratch_offset <= 0xFFFF:
        raise ValueError("scratch offset must fit u16")
    if not 1 <= record_bytes <= 0xFFFF:
        raise ValueError("record size must fit a non-zero u16")
    if not 1 <= bank_count <= 9:
        raise ValueError("bank count must be 1..9 (single-digit CJB1 filenames)")
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
    helper = bytes.fromhex(
        "80 7E F6 5E "             # current source byte == '^'
        "75 02 46 46 "             # two extra increments for a triple
        "46 3B 76 F4 C3"           # common increment, loop cmp, return
    )
    if EBOX_LAYOUT_LOCALS + len(initialization) != EBOX_ADVANCE_HELPER:
        raise ValueError("EBOX initialization does not meet embedded helper")
    payload = initialization + helper
    expected = 0x0297 - EBOX_LAYOUT_LOCALS
    if len(payload) != expected:
        raise ValueError(f"EBOX local/helper block is {len(payload)} bytes, expected {expected}")
    return payload


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


def patches(
    cache: bytes, line_gap: int = 0, cjk_draw_height: int = 9, bank_count: int = 4
) -> dict[int, tuple[bytes, bytes]]:
    if not 1 <= bank_count <= 9:
        raise ValueError("bank count must be 1..9 (single-digit CJB1 filenames)")
    resolve = resolver()
    state = bytes.fromhex("FF 00 FF FF 00 00 00 00 00 00 00 00 00 00")
    # DOS does not require a filename extension; dropping ".BIN" keeps each
    # entry to 3 bytes ("C{n}\0") so the table still fits between NAMES and
    # the resolver stub at COMMON even past four banks.
    filenames = tuple(f"C{bank}\0".encode("ascii") for bank in range(bank_count))
    table_bytes = bank_count * 2
    offset = NAMES + table_bytes
    name_offsets = []
    for filename in filenames:
        name_offsets.append(offset)
        offset += len(filename)
    names = struct.pack(f"<{bank_count}H", *name_offsets) + b"".join(filenames)
    if NAMES + len(names) > min(CACHE, COMMON):
        raise ValueError(
            f"bank name table for {bank_count} banks ends at 0x{NAMES + len(names):04X}, "
            f"beyond the resolver stub start 0x{COMMON:04X}"
        )
    result = {
        CODE_BASE + 0x094A: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 59 4A")),
        CODE_BASE + 0x07F8: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 CB 4B")),
        CODE_BASE + 0x09A2: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 41 4A")),
        CODE_BASE + 0x53A6: (bytes(16), triple_wrapper(0x53A6, 0xFA)),
        CODE_BASE + 0x53C6: (bytes(16), triple_wrapper(0x53C6, 0x06)),
        CODE_BASE + 0x53E6: (bytes(16), triple_wrapper(0x53E6, 0xF6)),
        CODE_BASE + STATE: (bytes(len(state)), state),
        CODE_BASE + NAMES: (bytes(len(names)), names),
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
    }
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
    return result


def patch_executable(
    source: bytes,
    scratch_offset: int = 0x3640,
    record_bytes: int = 242,
    line_gap: int = 0,
    cjk_draw_height: int = 9,
    bank_count: int = 4,
) -> tuple[bytes, bytes]:
    """Return a verified scratch-cache executable image and assembled cache."""
    data = bytearray(source)
    cache = assemble_cache(scratch_offset, record_bytes, bank_count)
    if CACHE + len(cache) > CACHE_RUNTIME_LIMIT:
        raise ValueError(
            f"resident cache ends at 0x{CACHE + len(cache):04X}, "
            f"beyond runtime-safe boundary 0x{CACHE_RUNTIME_LIMIT:04X}"
        )
    planned = patches(cache, line_gap, cjk_draw_height, bank_count)
    relocations = mz_relocation_file_offsets(source)
    relocated_bytes = relocations | {offset + 1 for offset in relocations}
    for offset, (_, replacement) in planned.items():
        overlap = sorted(set(range(offset, offset + len(replacement))) & relocated_bytes)
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
    result = bytes(data)
    for offset, (_, replacement) in planned.items():
        if result[offset : offset + len(replacement)] != replacement:
            raise ValueError(f"patched bytes failed verification at 0x{offset:05X}")
    return result, cache


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch-offset", type=lambda value: int(value, 0), default=0x3640)
    parser.add_argument("--record-bytes", type=lambda value: int(value, 0), default=242)
    parser.add_argument("--line-gap", type=int, default=0)
    args = parser.parse_args()
    data, cache = patch_executable(
        args.exe.read_bytes(), args.scratch_offset, args.record_bytes, args.line_gap
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
