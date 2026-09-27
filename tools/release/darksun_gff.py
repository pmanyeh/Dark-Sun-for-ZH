"""Read the chunk table of a Dark Sun GFF file (standard library only).

Ships in the release package, where gff-cat is not available. Layout per
vendor/opends/docs/file-formats.md section 1: a 28-byte header (``GFFI``,
version, data location, TOC location, TOC length, ...), then at the TOC a
header (types offset, free list offset) and the type list. Each type holds
indexed (id, location, length) records, or, when its count has the high bit
set, segment runs whose (location, length) pairs live in a secondary table
inside one of the file's GFFI chunks.
"""

from __future__ import annotations

import struct

SEGMENTED = 0x80000000


def gff_chunks(data: bytes) -> list[tuple[str, int, int, int]]:
    """(kind, id, file offset, length) for every chunk, in TOC order."""
    if data[:4] != b"GFFI":
        raise ValueError("not a GFF file")
    toc = struct.unpack_from("<I", data, 12)[0]
    types_offset = struct.unpack_from("<I", data, toc)[0]
    cursor = toc + types_offset
    (type_count,) = struct.unpack_from("<H", data, cursor)
    cursor += 2
    indexed: list[tuple[str, int, int, int]] = []
    segmented: list[tuple[str, int, list[tuple[int, int]]]] = []
    for _ in range(type_count):
        kind = data[cursor:cursor + 4].decode("latin-1").rstrip(" ")
        (count,) = struct.unpack_from("<I", data, cursor + 4)
        cursor += 8
        if count & SEGMENTED:
            _, table_index, run_count = struct.unpack_from("<iiI", data, cursor)
            cursor += 12
            runs = [struct.unpack_from("<ii", data, cursor + 8 * run) for run in range(run_count)]
            cursor += 8 * run_count
            segmented.append((kind, table_index, runs))
        else:
            for _ in range(count):
                chunk_id, offset, length = struct.unpack_from("<iII", data, cursor)
                cursor += 12
                indexed.append((kind, chunk_id, offset, length))
    gffi = [chunk for chunk in indexed if chunk[0] == "GFFI"]
    chunks = list(indexed)
    for kind, table_index, runs in segmented:
        _, _, table_offset, _ = gffi[table_index]
        (entries,) = struct.unpack_from("<I", data, table_offset)
        ids = [first + step for first, number in runs for step in range(number)]
        if len(ids) != entries:
            raise ValueError(f"{kind}: segment runs do not match the secondary table")
        for index, chunk_id in enumerate(ids):
            offset, length = struct.unpack_from("<II", data, table_offset + 4 + 8 * index)
            chunks.append((kind, chunk_id, offset, length))
    return chunks
