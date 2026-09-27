#!/usr/bin/env python3
"""Developer-side: assemble the portable release folder and its zip.

Run build_release_patches.py first (whenever the staging package changes);
this script refuses patch data built from a different staging. DOSBox-X and
the embeddable Python are extracted from the pinned, hash-checked downloads
cached in dist/_vendor_cache/ (vendor_dosboxx.py / vendor_python_embed.py).

usage: python tools/release/package_release.py
"""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

import vendor_dosboxx  # noqa: E402
import vendor_python_embed  # noqa: E402
from release_config import BUILD_DIR, RELEASE_DIR, RELEASE_LABEL, RELEASE_VERSION, STAGING, TEMPLATES  # noqa: E402
from tools.build_cjk_display_staging import PLAYER_GUIDE, player_guide_text  # noqa: E402

RUNTIME_SCRIPTS = ("installer.py", "bspatch_apply.py", "darksun_gff.py", "darksun_saves.py")
LAUNCHERS = {
    "install_launcher.bat.template": "安裝中文化.bat",
    "play_launcher.bat.template": "玩遊戲.bat",
    "uninstall_launcher.bat.template": "解除中文化.bat",
}
GAME_DATA_NOTE = "把DARKSUN資料夾放在這裡.txt"
GAME_DATA_TEXT = (
    "請把 Steam 版遊戲的整個 DARKSUN 資料夾複製到這個 game_data 資料夾裡，\r\n"
    "完成後應該是：game_data\\DARKSUN\\DSUN.EXE\r\n"
    "然後回到上一層，雙擊「安裝中文化.bat」。詳見 README_安裝說明.txt。\r\n"
)


def write_text(path: Path, text: str, *, bom: bool) -> None:
    body = text.replace("\r\n", "\n").replace("\n", "\r\n")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8"))


def main() -> int:
    manifest_path = BUILD_DIR / "release_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit("找不到 dist/_release_build：請先執行 build_release_patches.py")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["staging"] != STAGING.name or manifest["version"] != RELEASE_VERSION:
        raise SystemExit(f"補丁資料來自 {manifest['staging']} / {manifest['version']}，"
                         f"和設定的 {STAGING.name} / {RELEASE_VERSION} 不同：請重跑 build_release_patches.py")

    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)
    RELEASE_DIR.mkdir(parents=True)
    vendor_dosboxx.extract_dosboxx(vendor_dosboxx.download_asset(), RELEASE_DIR / "dosbox-x")
    vendor_python_embed.extract_python_embed(vendor_python_embed.download_asset(), RELEASE_DIR / "python-embed")

    for name in RUNTIME_SCRIPTS:
        shutil.copy2(HERE / name, RELEASE_DIR / name)
    for name in ("release_manifest.json", "save_migration.json"):
        shutil.copy2(BUILD_DIR / name, RELEASE_DIR / name)
    shutil.copytree(BUILD_DIR / "patches", RELEASE_DIR / "patches")
    shutil.copytree(BUILD_DIR / "resources", RELEASE_DIR / "resources")

    for template, target in LAUNCHERS.items():
        write_text(RELEASE_DIR / target, (TEMPLATES / template).read_text(encoding="utf-8"), bom=False)
    write_text(RELEASE_DIR / "dosbox-x" / "zh_darksun.conf",
               (TEMPLATES / "dosbox_darksun.conf.template").read_text(encoding="utf-8"), bom=False)
    readme = (TEMPLATES / "README_安裝說明.txt.template").read_text(encoding="utf-8").format(label=RELEASE_LABEL)
    write_text(RELEASE_DIR / "README_安裝說明.txt", readme, bom=True)
    write_text(RELEASE_DIR / "新操作說明.txt", player_guide_text(PLAYER_GUIDE.read_text(encoding="utf-8")), bom=True)
    shutil.copy2(TEMPLATES / "LICENSE_Fusion_Pixel_Font.txt", RELEASE_DIR / "LICENSE_Fusion_Pixel_Font.txt")

    game_data = RELEASE_DIR / "game_data"
    game_data.mkdir()
    write_text(game_data / GAME_DATA_NOTE, GAME_DATA_TEXT, bom=True)
    # Safety: nothing but the note may ever ship in game_data.
    stray = [path.name for path in game_data.iterdir() if path.name != GAME_DATA_NOTE]
    if stray:
        raise SystemExit(f"game_data 裡有不該發布的檔案：{stray}")
    for path in RELEASE_DIR.rglob("*"):
        if path.is_file() and path.suffix.upper() in (".SAV", ".GFF") or path.name.upper() == "DSUN.EXE":
            raise SystemExit(f"整合包裡出現遊戲檔案：{path}")

    archive = RELEASE_DIR.parent / f"{RELEASE_DIR.name}.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(RELEASE_DIR.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                bundle.write(path, Path(RELEASE_DIR.name) / path.relative_to(RELEASE_DIR))
    print(f"[OK] {RELEASE_DIR}")
    print(f"[OK] {archive} ({archive.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
