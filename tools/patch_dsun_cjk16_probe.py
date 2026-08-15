"""Install the independent-CJK-table compatibility-trampoline probe.

Six explicit two-byte codes become CJK ids 0, 1, 2, 256, 257, and 258. A common resolver looks
the id up in the appended CJK1 table, writes that record offset into one
temporary legacy marker entry (0x7F), and returns the marker to the unchanged
FONT renderer.  The marker is a trampoline, not the glyph identity: every
pair is selected from the independent CJK table with a 16-bit AX index.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "scratch_test/font_16x15_experiment/DARKSUN/DSUN.EXE"
CODE_BASE = 0x33C60
COMMON = 0x5420
PAIR_TABLE = 0x54D0
EXTENSION_BASE = 0x3640
EXTENSION_TABLE = 0x3650
MARKER = 0x7F
MARKER_ENTRY = 0x108 + MARKER * 2


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


DEFAULT_PAIR_RECORDS = bytes.fromhex(
    "7B 21 00 00 7B 24 01 00 7B 26 02 00 7D 65 00 01 7D 66 01 01 7D 67 02 01"
)
CONTROL_PAIR_IDS = (0, 124, 125, 249, 34, 35, 875, 999, 1625, 1749, 3375, 3499)
PRINTABLE_TRIPLE_IDS = (0, 93, 94, 187, 4418, 4511, 8742, 8835, 255, 256, 880, 881)
ALGORITHMIC_TRIPLE_IDS = PRINTABLE_TRIPLE_IDS


def control_pair_records() -> bytes:
    try:
        from .cjk_localization_pipeline import pair_for_id
    except ImportError:
        from cjk_localization_pipeline import pair_for_id

    return b"".join(pair_for_id(cjk_id) + struct.pack("<H", cjk_id) for cjk_id in CONTROL_PAIR_IDS)


def common_resolver(pair_count: int = 6) -> bytes:
    code = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str]] = []

    def emit(hex_bytes: str) -> None:
        code.extend(bytes.fromhex(hex_bytes))

    def label(name: str) -> None:
        labels[name] = len(code)

    def jcc(opcode: int, target: str) -> None:
        fixups.append((len(code), target))
        code.extend((opcode, 0))

    emit("26 8B 17")          # mov dx,es:[bx] (candidate pair)
    emit("56 51")             # push si; push cx
    emit(f"BE {PAIR_TABLE & 0xFF:02X} {PAIR_TABLE >> 8:02X}")
    emit(f"B9 {pair_count & 0xFF:02X} {pair_count >> 8:02X}")
    label("search")
    emit("2E 3B 14")          # cmp dx,cs:[si]
    jcc(0x74, "found")
    emit("83 C6 04")          # add si,4
    jcc(0xE2, "search")       # loop search
    emit("59 5E")             # pop cx; pop si
    emit("26 8A 07 30 E4 C3") # ordinary byte, AH=0
    label("found")
    emit("2E 8B 44 02")       # mov ax,cs:[si+2] (u16 CJK id)
    emit("59 5E")             # pop cx; pop si
    emit("53 06 52 51 56")    # preserve bx,es,dx,cx,si
    emit("8B F0")             # mov si,ax
    emit("C4 1E 78 A3")       # les bx,[A378]
    emit("8B C6 8A C4 30 E4 D1 E0") # AX=(id>>8)*2
    emit(f"81 C3 {EXTENSION_TABLE & 0xFF:02X} {EXTENSION_TABLE >> 8:02X}")
    emit("03 D8")             # add bx,ax
    emit("26 8B 0F")          # mov cx,es:[bx] (bank-relative offset)
    emit("8B 1E 78 A3")       # mov bx,[A378]
    emit(f"81 C3 {EXTENSION_BASE & 0xFF:02X} {EXTENSION_BASE >> 8:02X}")
    emit("03 D9")             # add bx,cx (runtime bank start)
    emit("8B C6 30 E4 D1 E0") # AX=(id&0xff)*2
    emit("83 C3 04 03 D8")    # bank table starts at +4; add index
    emit("26 8B 17")          # mov dx,es:[bx] (bank-relative record)
    emit("03 D1")             # add dx,cx (extension-relative bank + record)
    emit(f"81 C2 {EXTENSION_BASE & 0xFF:02X} {EXTENSION_BASE >> 8:02X}")
    emit("8B 1E 78 A3")       # mov bx,[A378]
    emit(f"26 89 97 {MARKER_ENTRY & 0xFF:02X} {MARKER_ENTRY >> 8:02X}")
    emit("5E 59 5A 07 5B")    # restore si,cx,dx,es,bx
    emit(f"B8 {MARKER:02X} 01")  # AL=marker, AH=pair flag
    emit("C3")

    for position, target in fixups:
        displacement = labels[target] - (position + 2)
        if not -128 <= displacement <= 127:
            raise ValueError("short branch out of range")
        code[position + 1] = displacement & 0xFF
    return bytes(code)


def printable_triple_for_id(cjk_id: int) -> bytes:
    try:
        from .cjk_localization_pipeline import transport_for_id
    except ImportError:
        from cjk_localization_pipeline import transport_for_id

    return transport_for_id(cjk_id)


def printable_triple_records() -> bytes:
    return b"".join(
        printable_triple_for_id(cjk_id) + struct.pack("<H", cjk_id)
        for cjk_id in PRINTABLE_TRIPLE_IDS
    )


def triple_resolver(record_count: int) -> bytes:
    code = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str]] = []

    def emit(hex_bytes: str) -> None:
        code.extend(bytes.fromhex(hex_bytes))

    def label(name: str) -> None:
        labels[name] = len(code)

    def jcc(opcode: int, target: str) -> None:
        fixups.append((len(code), target))
        code.extend((opcode, 0))

    emit("26 8B 17")          # mov dx,es:[bx] (prefix + first digit)
    emit("56 51")             # push si; push cx
    emit(f"BE {PAIR_TABLE & 0xFF:02X} {PAIR_TABLE >> 8:02X}")
    emit(f"B9 {record_count & 0xFF:02X} {record_count >> 8:02X}")
    label("search")
    emit("2E 3B 14")          # cmp dx,cs:[si]
    jcc(0x75, "next")
    emit("26 8A 47 02")       # mov al,es:[bx+2]
    emit("2E 3A 44 02")       # cmp al,cs:[si+2]
    jcc(0x74, "found")
    label("next")
    emit("83 C6 05")          # add si,5
    jcc(0xE2, "search")
    emit("59 5E")
    emit("26 8A 07 30 E4 C3") # ordinary byte
    label("found")
    emit("2E 8B 44 03")       # mov ax,cs:[si+3] (u16 CJK id)
    emit("59 5E")
    emit("53 06 52 51 56")
    emit("8B F0")
    emit("C4 1E 78 A3")
    emit("8B C6 8A C4 30 E4 D1 E0")
    emit(f"81 C3 {EXTENSION_TABLE & 0xFF:02X} {EXTENSION_TABLE >> 8:02X}")
    emit("03 D8 26 8B 0F")
    emit("8B 1E 78 A3")
    emit(f"81 C3 {EXTENSION_BASE & 0xFF:02X} {EXTENSION_BASE >> 8:02X}")
    emit("03 D9")
    emit("8B C6 30 E4 D1 E0")
    emit("83 C3 04 03 D8")
    emit("26 8B 17 03 D1")
    emit(f"81 C2 {EXTENSION_BASE & 0xFF:02X} {EXTENSION_BASE >> 8:02X}")
    emit("8B 1E 78 A3")
    emit(f"26 89 97 {MARKER_ENTRY & 0xFF:02X} {MARKER_ENTRY >> 8:02X}")
    emit("5E 59 5A 07 5B")
    emit(f"B8 {MARKER:02X} 01 C3")

    for position, target in fixups:
        displacement = labels[target] - (position + 2)
        if not -128 <= displacement <= 127:
            raise ValueError("short branch out of range")
        code[position + 1] = displacement & 0xFF
    return bytes(code)


def algorithmic_triple_resolver() -> bytes:
    code = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str]] = []

    def emit(hex_bytes: str) -> None:
        code.extend(bytes.fromhex(hex_bytes))

    def label(name: str) -> None:
        labels[name] = len(code)

    def jcc(opcode: int, target: str) -> None:
        fixups.append((len(code), target))
        code.extend((opcode, 0))

    emit("26 8A 07")          # mov al,es:[bx]
    emit("3C 5E")             # cmp al,'^'
    jcc(0x75, "ordinary")
    emit("26 8A 47 01")       # mov al,es:[bx+1]
    emit("2C 21 3C 5D")       # subtract '!'; require 0..93
    jcc(0x77, "ordinary")
    emit("30 E4")             # xor ah,ah
    emit("B2 5E F6 E2")       # mov dl,94; mul dl -> AX
    emit("26 8A 57 02")       # mov dl,es:[bx+2]
    emit("80 EA 21 80 FA 5D") # subtract '!'; require 0..93
    jcc(0x77, "ordinary")
    emit("30 F6 03 C2")       # xor dh,dh; add ax,dx
    emit("3D A3 16")          # reserve '^^^' / ID 5795
    jcc(0x74, "reserved")
    emit("53 06 52 51 56")
    emit("8B F0")             # mov si,ax (dynamic ID checkpoint)
    emit("C4 1E 78 A3")
    emit("8B C6 8A C4 30 E4 D1 E0")
    emit(f"81 C3 {EXTENSION_TABLE & 0xFF:02X} {EXTENSION_TABLE >> 8:02X}")
    emit("03 D8 26 8B 0F")
    emit("8B 1E 78 A3")
    emit(f"81 C3 {EXTENSION_BASE & 0xFF:02X} {EXTENSION_BASE >> 8:02X}")
    emit("03 D9")
    emit("8B C6 30 E4 D1 E0")
    emit("83 C3 04 03 D8")
    emit("26 8B 17 03 D1")
    emit(f"81 C2 {EXTENSION_BASE & 0xFF:02X} {EXTENSION_BASE >> 8:02X}")
    emit("8B 1E 78 A3")
    emit(f"26 89 97 {MARKER_ENTRY & 0xFF:02X} {MARKER_ENTRY >> 8:02X}")
    emit("5E 59 5A 07 5B")
    emit(f"B8 {MARKER:02X} 01 C3")
    label("reserved")
    emit("B8 3F 01 C3")       # one '?' replacement; consume the full triple
    label("ordinary")
    emit("26 8A 07 30 E4 C3")

    for position, target in fixups:
        displacement = labels[target] - (position + 2)
        if not -128 <= displacement <= 127:
            raise ValueError("short branch out of range")
        code[position + 1] = displacement & 0xFF
    return bytes(code)


def wrapper(address: int, pointer_displacement: int) -> bytes:
    displacement = (COMMON - (address + 3)) & 0xFFFF
    # call common; or ah,ah; jz no_inc; inc pointer; xor ah,ah; ret
    return (
        b"\xE8" + struct.pack("<H", displacement)
        + bytes.fromhex("08 E4 74 03 FF 46") + bytes([pointer_displacement])
        + bytes.fromhex("30 E4 C3")
    )


def triple_wrapper(address: int, pointer_displacement: int) -> bytes:
    displacement = (COMMON - (address + 3)) & 0xFFFF
    return (
        b"\xE8" + struct.pack("<H", displacement)
        + bytes.fromhex("08 E4 74 06 FF 46") + bytes([pointer_displacement])
        + bytes.fromhex("FF 46") + bytes([pointer_displacement])
        + bytes.fromhex("30 E4 C3")
    )


def make_patches(pair_records: bytes) -> dict[int, tuple[bytes, bytes]]:
    if not pair_records or len(pair_records) % 4:
        raise ValueError("pair records must contain one 4-byte pair/id record per entry")
    pair_count = len(pair_records) // 4
    resolver = common_resolver(pair_count)
    return {
        CODE_BASE + 0x094A: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 59 4A")),
        CODE_BASE + 0x07F8: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 CB 4B")),
        CODE_BASE + 0x09A2: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 41 4A")),
        CODE_BASE + 0x53A6: (bytes(13), wrapper(0x53A6, 0xFA)),
        CODE_BASE + 0x53C6: (bytes(13), wrapper(0x53C6, 0x06)),
        CODE_BASE + 0x53E6: (bytes(13), wrapper(0x53E6, 0xF6)),
        CODE_BASE + COMMON: (bytes(len(resolver)), resolver),
        CODE_BASE + PAIR_TABLE: (bytes(len(pair_records)), pair_records),
    }


def make_triple_patches(records: bytes) -> dict[int, tuple[bytes, bytes]]:
    if not records or len(records) % 5:
        raise ValueError("triple records must contain one 5-byte key/id record per entry")
    count = len(records) // 5
    resolver = triple_resolver(count)
    return {
        CODE_BASE + 0x094A: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 59 4A")),
        CODE_BASE + 0x07F8: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 CB 4B")),
        CODE_BASE + 0x09A2: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 41 4A")),
        CODE_BASE + 0x53A6: (bytes(16), triple_wrapper(0x53A6, 0xFA)),
        CODE_BASE + 0x53C6: (bytes(16), triple_wrapper(0x53C6, 0x06)),
        CODE_BASE + 0x53E6: (bytes(16), triple_wrapper(0x53E6, 0xF6)),
        CODE_BASE + COMMON: (bytes(len(resolver)), resolver),
        CODE_BASE + PAIR_TABLE: (bytes(len(records)), records),
    }


def make_algorithmic_patches() -> dict[int, tuple[bytes, bytes]]:
    resolver = algorithmic_triple_resolver()
    return {
        CODE_BASE + 0x094A: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 59 4A")),
        CODE_BASE + 0x07F8: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 CB 4B")),
        CODE_BASE + 0x09A2: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 41 4A")),
        CODE_BASE + 0x53A6: (bytes(16), triple_wrapper(0x53A6, 0xFA)),
        CODE_BASE + 0x53C6: (bytes(16), triple_wrapper(0x53C6, 0x06)),
        CODE_BASE + 0x53E6: (bytes(16), triple_wrapper(0x53E6, 0xF6)),
        CODE_BASE + COMMON: (bytes(len(resolver)), resolver),
    }


def install(
    exe: Path,
    pair_records: bytes = DEFAULT_PAIR_RECORDS,
    triple: bool = False,
    algorithmic: bool = False,
) -> None:
    backup = exe.with_suffix(exe.suffix + ".cjk16-probe.bak")
    data = bytearray(exe.read_bytes())
    if algorithmic:
        patches = make_algorithmic_patches()
    else:
        patches = make_triple_patches(pair_records) if triple else make_patches(pair_records)
    for offset, (original, patched) in patches.items():
        current = bytes(data[offset : offset + len(original)])
        if current != original:
            raise ValueError(f"unexpected bytes at 0x{offset:05X}: {current.hex()}")
    if not backup.exists():
        shutil.copy2(exe, backup)
    elif backup.read_bytes() != data:
        raise ValueError("existing CJK16 backup does not match the input executable")
    for offset, (_, patched) in patches.items():
        data[offset : offset + len(patched)] = patched
    exe.write_bytes(data)
    print(f"patched={exe}")
    record_size = 5 if triple else 4
    print(f"pair_count={'algorithmic' if algorithmic else len(pair_records) // record_size}")
    if algorithmic:
        resolver_size = len(algorithmic_triple_resolver())
    else:
        resolver_size = len(triple_resolver(len(pair_records) // 5)) if triple else len(common_resolver(len(pair_records) // 4))
    print(f"common_size={resolver_size}")
    print(f"sha256={sha256(bytes(data))}")


def restore(exe: Path) -> None:
    backup = exe.with_suffix(exe.suffix + ".cjk16-probe.bak")
    shutil.copy2(backup, exe)
    print(f"restored={exe}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--control-transport", action="store_true")
    parser.add_argument("--printable-triple", action="store_true")
    parser.add_argument("--algorithmic-triple", action="store_true")
    args = parser.parse_args()
    if args.restore:
        restore(args.exe.resolve())
    else:
        if sum((args.control_transport, args.printable_triple, args.algorithmic_triple)) > 1:
            parser.error("choose only one transport probe")
        if args.algorithmic_triple:
            install(args.exe.resolve(), algorithmic=True)
        elif args.printable_triple:
            install(args.exe.resolve(), printable_triple_records(), triple=True)
        else:
            records = control_pair_records() if args.control_transport else DEFAULT_PAIR_RECORDS
            install(args.exe.resolve(), records)


if __name__ == "__main__":
    main()
