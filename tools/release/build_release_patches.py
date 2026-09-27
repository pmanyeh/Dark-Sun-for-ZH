#!/usr/bin/env python3
"""Developer-side: turn the verified staging package into release patch data.

Writes to dist/_release_build/:

* patches/<FILE>.bsdiff  -- BSDIFF40 patches from each supported edition's original
  file to the staging file (bsdiff4 is a developer-only dependency).
* resources/C0..C11      -- the Chinese font banks (new files, copied as they are).
* save_migration.json    -- precomputed Chinese bytes for old saves (darksun_saves.py).
* release_manifest.json  -- per edition and file: source/target sha256, patch name.

Every patch is applied back with the release's own bspatch_apply.py and must
reproduce the staging file byte for byte before anything is written.

usage: python tools/release/build_release_patches.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

try:
    import bsdiff4
except ImportError as exc:  # pragma: no cover
    raise SystemExit("This developer tool needs bsdiff4: pip install bsdiff4") from exc

from bspatch_apply import apply_patch  # noqa: E402
from release_config import (  # noqa: E402
    BUILD_DIR, FONT_BANKS, GPL_PACKAGE, PATCHED_FILES, RELEASE_VERSION, SOURCE_EDITIONS, STAGING, STAGING_GAME,
)
from tools.cjk_localization_pipeline import DEFAULT_MAPPING, load_mapping  # noqa: E402
from tools.creature_name_layer import encoded_name, load_creature_names  # noqa: E402

# GSTR index -> MAS-99 string copy offset (tools/patch_save_gstr.py).
GSTR_SOURCES = {1: 0, 5: 20, 6: 33, 7: 66, 4: 96}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_migration() -> dict:
    package = json.loads(GPL_PACKAGE.read_text(encoding="utf-8"))
    by_offset = {edit["original_offset"]: edit for edit in package["edits"]
                 if edit["kind"] == "MAS" and edit["chunk_id"] == 99}
    gstr = {str(index): [by_offset[offset]["original"], by_offset[offset]["encoded_ascii"]]
            for index, offset in GSTR_SOURCES.items()}
    mapping = load_mapping(DEFAULT_MAPPING)
    names = {english: encoded_name(chinese, mapping).hex() for english, chinese in load_creature_names().items()}
    return {"gstr": gstr, "creature_names": names}


def main() -> int:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    (BUILD_DIR / "patches").mkdir(parents=True)
    (BUILD_DIR / "resources").mkdir()
    manifest: dict = {
        "format": "darksun-zh-release",
        "version": RELEASE_VERSION,
        "staging": STAGING.name,
        "editions": {},
        "font_banks": {},
    }
    for edition, source_dir in SOURCE_EDITIONS.items():
        files = {}
        for name in PATCHED_FILES:
            original = (source_dir / name).read_bytes()
            target = (STAGING_GAME / name).read_bytes()
            patch = bsdiff4.diff(original, target)
            if apply_patch(original, patch) != target:
                raise SystemExit(f"{edition} {name}: the patch does not reproduce the staging file")
            patch_name = f"{edition}_{name}.bsdiff"
            (BUILD_DIR / "patches" / patch_name).write_bytes(patch)
            files[name] = {
                "source_sha256": sha256(original),
                "target_sha256": sha256(target),
                "patch": patch_name,
            }
            print(f"{edition} {name}: {len(original)} -> {len(target)} bytes, patch {len(patch)} bytes")
        manifest["editions"][edition] = files
    for name in FONT_BANKS:
        data = (STAGING_GAME / name).read_bytes()
        (BUILD_DIR / "resources" / name).write_bytes(data)
        manifest["font_banks"][name] = sha256(data)
    migration = save_migration()
    (BUILD_DIR / "save_migration.json").write_text(json.dumps(migration, ensure_ascii=False, indent=1), encoding="utf-8")
    (BUILD_DIR / "release_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"font banks: {len(FONT_BANKS)}, creature names: {len(migration['creature_names'])}")
    print(f"[OK] {BUILD_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
