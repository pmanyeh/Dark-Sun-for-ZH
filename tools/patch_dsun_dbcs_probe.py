"""Install or restore the DSUN.EXE multi-pair glyph probe.

The probe maps ``~A`` through ``~F`` to the six FONT-100 slots used by the
16x15 ``中文顯示成功`` experiment.  Each pair is consumed as one character.
It patches only the ignored 16x15 experiment copy of DSUN.EXE, never the
source game installation.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "scratch_test/font_16x15_experiment/DARKSUN/DSUN.EXE"
CODE_SEGMENT_FILE_BASE = 0x33C60


def helper(pointer_displacement: int) -> bytes:
    # Keep ordinary bytes unchanged.  For ~A..~F, use the trail byte as an
    # index into the shared six-byte glyph table and consume it here; the
    # original caller performs the lead-byte increment after return.
    return (
        bytes.fromhex(
            "26 8A 07 3C 7E 75 17 26 8A 47 01 2C 41 3C 05 77 0B "
            "53 BB 10 54 2E D7 5B FF 46"
        )
        + bytes([pointer_displacement])
        + bytes.fromhex("C3 B0 7E C3")
    )


PATCHES = {
    # Replace three-byte byte-loads with same-segment near calls.
    CODE_SEGMENT_FILE_BASE + 0x094A: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 59 4A")),
    CODE_SEGMENT_FILE_BASE + 0x07F8: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 CB 4B")),
    CODE_SEGMENT_FILE_BASE + 0x09A2: (bytes.fromhex("26 8A 07"), bytes.fromhex("E8 41 4A")),
    # Renderer, width calculator, and formatted-string helpers.
    CODE_SEGMENT_FILE_BASE + 0x53A6: (bytes(31), helper(0xFA)),  # [bp-06]
    CODE_SEGMENT_FILE_BASE + 0x53C6: (bytes(31), helper(0x06)),  # [bp+06]
    CODE_SEGMENT_FILE_BASE + 0x53E6: (bytes(31), helper(0xF6)),  # [bp-0A]
    # ~A uses marker 0xFF, whose FONT offset-table entry points beyond the
    # legacy payload to the appended CJK1 record.  ~B..~F retain legacy slots.
    CODE_SEGMENT_FILE_BASE + 0x5410: (bytes(6), bytes.fromhex("FF 23 24 5B 5D 2A")),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def install(exe: Path) -> None:
    backup = exe.with_suffix(exe.suffix + ".dbcs-probe.bak")
    data = bytearray(exe.read_bytes())

    states = []
    for offset, (original, patched) in PATCHES.items():
        current = bytes(data[offset : offset + len(original)])
        if current == original:
            states.append("original")
        elif current == patched:
            states.append("patched")
        else:
            raise ValueError(
                f"unexpected bytes at 0x{offset:05X}: "
                f"expected {original.hex()} or {patched.hex()}, got {current.hex()}"
            )

    if all(state == "patched" for state in states):
        print(f"already patched: {exe}")
        print(f"sha256={sha256(data)}")
        return
    if any(state == "patched" for state in states):
        raise ValueError("refusing to continue from a partially patched executable")

    if not backup.exists():
        shutil.copy2(exe, backup)
        print(f"backup={backup}")
        print(f"backup_sha256={sha256(backup.read_bytes())}")
    elif backup.read_bytes() != data:
        raise ValueError(f"existing backup does not match the unpatched executable: {backup}")

    for offset, (_, patched) in PATCHES.items():
        data[offset : offset + len(patched)] = patched
    exe.write_bytes(data)

    verified = exe.read_bytes()
    for offset, (_, patched) in PATCHES.items():
        if verified[offset : offset + len(patched)] != patched:
            raise ValueError(f"verification failed at 0x{offset:05X}")
    print(f"patched={exe}")
    print(f"sha256={sha256(verified)}")


def restore(exe: Path) -> None:
    backup = exe.with_suffix(exe.suffix + ".dbcs-probe.bak")
    if not backup.exists():
        raise FileNotFoundError(f"backup not found: {backup}")
    shutil.copy2(backup, exe)
    print(f"restored={exe}")
    print(f"sha256={sha256(exe.read_bytes())}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    (restore if args.restore else install)(args.exe.resolve())


if __name__ == "__main__":
    main()
