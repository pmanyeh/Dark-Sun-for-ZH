#!/usr/bin/env python3
"""Give old saves the Chinese creature names (creature_name_layer.py).

A save keeps the combat records of the current region (SAVE/5) and of the
regions already visited, names included, so creatures loaded before the
SEGOBJEX.GFF names changed would stay English. This rewrites every name
field whose English is in creature_names.csv, in SAVE*.SAV and DARKRUN.GFF.
The first change of a file keeps a copy as *.names.orig; running it again
finds nothing left to change.

usage: patch_save_creature_names.py <GAME/DARKSUN directory>
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

try:
    from .cjk_localization_pipeline import DEFAULT_GFF_CAT, DEFAULT_MAPPING, load_mapping
    from .creature_name_layer import changed_ranges_are_names, gff_chunks, load_creature_names, patch_save_records
except ImportError:
    from cjk_localization_pipeline import DEFAULT_GFF_CAT, DEFAULT_MAPPING, load_mapping
    from creature_name_layer import changed_ranges_are_names, gff_chunks, load_creature_names, patch_save_records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("game", type=Path)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--gff-cat", type=Path, default=DEFAULT_GFF_CAT)
    args = parser.parse_args()

    mapping = load_mapping(args.mapping)
    names = load_creature_names()
    for path in sorted(args.game.glob("SAVE*.SAV")) + [args.game / "DARKRUN.GFF"]:
        if not path.is_file():
            continue
        data = path.read_bytes()
        patched, renamed = patch_save_records(data, gff_chunks(args.gff_cat, path), names, mapping)
        if not changed_ranges_are_names(data, patched, [start for start, *_ in renamed]):
            raise ValueError(f"{path.name}: changed outside the creature name fields")
        if renamed:
            backup = path.with_name(path.name + ".names.orig")
            if not backup.exists():
                shutil.copy2(path, backup)
            path.write_bytes(patched)
        print(f"{path.name}: {len(renamed)} name(s) rewritten "
              f"({len({english for _, _, english, _ in renamed})} distinct)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
