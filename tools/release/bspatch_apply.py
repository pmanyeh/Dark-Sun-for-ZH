"""Pure-stdlib apply side of the BSDIFF4 patch format (magic ``BSDIFF40``).

The `bsdiff4` PyPI package's diff algorithm is not pure Python (it ships a
compiled `core` extension), so it is only used on the developer side, in
`tools/release/build_exe_patch.py`, to *generate* patches. This module
reimplements just the *apply* side from the documented format so that
`installer.py` -- the script that ships to end users inside the release
package -- never requires `pip install`ing anything: only `bz2` and
`struct`, both in the standard library.

Format (see Colin Percival's original bsdiff, as used by python-bsdiff4):
    8 bytes   magic "BSDIFF40"
    8 bytes   length of bzip2'd control block   (signed, see decode_int64)
    8 bytes   length of bzip2'd diff block
    8 bytes   length of the (uncompressed) target file
    ...       bzip2'd control block: triples of (add_len, copy_len, seek_len),
              each int encoded as 8 bytes via encode_int64
    ...       bzip2'd diff block   (added byte-for-byte onto the source)
    ...       bzip2'd extra block  (copied verbatim into the target)

Verified against real `bsdiff4.diff()` output in this project's own
KRONDOR.EXE patch (v1.00 baseline -> translated build): byte-identical
round trip.
"""

from __future__ import annotations

import bz2

MAGIC = b"BSDIFF40"


def decode_int64(b: bytes) -> int:
    """Decode bsdiff's 8-byte little-endian magnitude+sign integer."""
    x = int.from_bytes(b[:8], "little")
    if x & (1 << 63):
        x = -(x & ~(1 << 63))
    return x


def _read_patch(patch_bytes: bytes) -> tuple[int, list[tuple[int, int, int]], bytes, bytes]:
    if patch_bytes[:8] != MAGIC:
        raise ValueError("Not a BSDIFF40 patch (bad magic header)")
    off = 8
    len_control = decode_int64(patch_bytes[off : off + 8])
    off += 8
    len_diff = decode_int64(patch_bytes[off : off + 8])
    off += 8
    len_dst = decode_int64(patch_bytes[off : off + 8])
    off += 8

    bcontrol_raw = patch_bytes[off : off + len_control]
    off += len_control
    bdiff_raw = patch_bytes[off : off + len_diff]
    off += len_diff
    bextra_raw = patch_bytes[off:]

    bcontrol = bz2.decompress(bcontrol_raw)
    tcontrol = [
        (
            decode_int64(bcontrol[i : i + 8]),
            decode_int64(bcontrol[i + 8 : i + 16]),
            decode_int64(bcontrol[i + 16 : i + 24]),
        )
        for i in range(0, len(bcontrol), 24)
    ]
    bdiff = bz2.decompress(bdiff_raw)
    bextra = bz2.decompress(bextra_raw)
    return len_dst, tcontrol, bdiff, bextra


def apply_patch(src_bytes: bytes, patch_bytes: bytes) -> bytes:
    """Apply a BSDIFF4-format patch to `src_bytes`, returning the target bytes."""
    len_dst, tcontrol, bdiff, bextra = _read_patch(patch_bytes)
    out = bytearray(len_dst)
    old_pos = 0
    new_pos = 0
    diff_pos = 0
    extra_pos = 0
    for add_len, copy_len, seek_len in tcontrol:
        for i in range(add_len):
            out[new_pos + i] = (src_bytes[old_pos + i] + bdiff[diff_pos + i]) & 0xFF
        new_pos += add_len
        old_pos += add_len
        diff_pos += add_len

        out[new_pos : new_pos + copy_len] = bextra[extra_pos : extra_pos + copy_len]
        new_pos += copy_len
        extra_pos += copy_len
        old_pos += seek_len
    return bytes(out)
