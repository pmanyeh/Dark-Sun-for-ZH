"""Bring saves made before the Chinese patch in line with it (standard library only).

A save keeps two kinds of English text the patched game data no longer has:

* The global strings GSTR[1], [4]..[7] (menu titles such as "What do you
  say?"), 42-byte slots seeded by MAS-99. Same logic as tools/patch_save_gstr.py.
* Creature names in the saved 0x3A-byte combat records (SAVE chunks), which
  the region loader copied from SEGOBJEX.GFF. Same logic as
  tools/creature_name_layer.patch_save_records.

The Chinese bytes come precomputed in save_migration.json (build_release_patches.py),
so this module needs neither the CJK mapping nor gff-cat. Running it again changes
nothing.
"""

from __future__ import annotations

from darksun_gff import gff_chunks

GSTR_SLOT = 42
COMBAT_RECORD = 0x3A
NAME_OFFSET = 0x28
NAME_BYTES = 16


def migrate_gstr(data: bytearray, gstr: dict[str, list[str]]) -> list[int]:
    """Rewrite English GSTR slots; ``gstr`` maps index -> [english, chinese] (ASCII)."""
    values = {int(index): (english.encode("ascii"), chinese.encode("ascii")) for index, (english, chinese) in gstr.items()}
    base = -1
    for index, (english, chinese) in sorted(values.items()):
        for candidate in (english, chinese):
            at = bytes(data).find(candidate + bytes(GSTR_SLOT - len(candidate)))
            if at >= 0:
                base = at - (index - 1) * GSTR_SLOT
                break
        if base >= 0:
            break
    if base < 0 or bytes(data[base + GSTR_SLOT:base + GSTR_SLOT + 4]) != b"END\0":
        return []
    changed = []
    for index, (english, chinese) in sorted(values.items()):
        start = base + (index - 1) * GSTR_SLOT
        slot = bytes(data[start:start + GSTR_SLOT])
        if slot == english.ljust(GSTR_SLOT, b"\0"):
            data[start:start + GSTR_SLOT] = chinese.ljust(GSTR_SLOT, b"\0")
            changed.append(index)
    return changed


def migrate_creature_names(data: bytearray, names: dict[str, str]) -> int:
    """Rewrite English creature names; ``names`` maps English -> 16-byte field as hex."""
    fields = {english: bytes.fromhex(value) for english, value in names.items()}
    changed = 0
    for kind, _, offset, length in gff_chunks(bytes(data)):
        if kind != "SAVE" or length == 0 or length % COMBAT_RECORD:
            continue
        for record in range(length // COMBAT_RECORD):
            start = offset + record * COMBAT_RECORD + NAME_OFFSET
            english = bytes(data[start:start + NAME_BYTES]).split(b"\0", 1)[0].decode("latin-1")
            if english in fields:
                data[start:start + NAME_BYTES] = fields[english]
                changed += 1
    return changed


def migrate_save(data: bytes, migration: dict) -> tuple[bytes, list[int], int]:
    patched = bytearray(data)
    gstr = migrate_gstr(patched, migration["gstr"])
    names = migrate_creature_names(patched, migration["creature_names"])
    return bytes(patched), gstr, names
