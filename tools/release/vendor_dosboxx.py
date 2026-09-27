"""Developer-side tool: bundle a portable DOSBox-X build into the release
package so end users don't have to separately find/install a DOS emulator.

Unlike the game itself, DOSBox-X (https://github.com/joncampbell123/dosbox-x)
is GPLv2-licensed free software -- its official prebuilt binaries can be
redistributed as long as the license text and a pointer to the source are
included, which this script does automatically (COPYING + NOTICE_DOSBOX-X.txt).

The release/version is pinned (not "latest") so builds stay reproducible; the
downloaded archive's sha256 is verified against the pinned value before
extracting. The download is cached under dist/_vendor_cache/ so re-running
this script (or package_release.py) doesn't re-fetch 40+ MB every time.

Usage:
    python tools/release/vendor_dosboxx.py
"""

from __future__ import annotations

import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = REPO_ROOT / "dist" / "_vendor_cache"
from release_config import RELEASE_DIR  # noqa: E402

DOSBOX_X_TAG = "dosbox-x-v2026.08.02"
ASSET_NAME = "dosbox-x-vsbuild-win64-2026.08.02-portable.zip"
ASSET_URL = f"https://github.com/joncampbell123/dosbox-x/releases/download/{DOSBOX_X_TAG}/{ASSET_NAME}"
ASSET_SHA256 = "ca28208f5fee25a74caf3a02cc0189c7f7943a42ce37c02848f5fc03450a96cf"

# Inside the zip, the actual runnable win64 build lives under this prefix.
ZIP_RELEASE_PREFIX = "bin/x64/Release/"

NOTICE_TEXT = f"""\
本資料夾內的 DOSBox-X 是原封不動的官方預先編譯版本，用來讓使用者不必自己
另外安裝 DOS 模擬器就能執行中文化後的《浩劫殘陽：破碎大地》。

DOSBox-X 是採用 GNU General Public License v2 授權的自由／開放原始碼軟體，
與本專案（浩劫殘陽：破碎大地 繁體中文化）完全獨立、沒有從屬關係。

  來源：https://github.com/joncampbell123/dosbox-x
  版本：{DOSBOX_X_TAG}
  發布檔案：{ASSET_NAME}
  SHA-256：{ASSET_SHA256}

完整授權條款請見同資料夾的 COPYING 檔案；原始碼可在上述來源網址取得。
"""


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_asset() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / ASSET_NAME
    if cached.exists() and sha256_of_file(cached) == ASSET_SHA256:
        print(f"[快取] 已有驗證過的 {cached}，略過下載")
        return cached

    print(f"下載 {ASSET_URL} ...")
    tmp = cached.with_suffix(".part")
    urllib.request.urlretrieve(ASSET_URL, tmp)  # noqa: S310 -- pinned https GitHub Releases URL

    actual_hash = sha256_of_file(tmp)
    if actual_hash != ASSET_SHA256:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"下載的檔案雜湊值不符，拒絕使用：\n  預期 {ASSET_SHA256}\n  實際 {actual_hash}")
    tmp.replace(cached)
    print(f"[OK] 下載並驗證完成：{cached}")
    return cached


def extract_dosboxx(zip_path: Path, dest_dir: Path) -> None:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extract("COPYING", dest_dir)
        (dest_dir / "COPYING_dosbox-x").write_bytes((dest_dir / "COPYING").read_bytes())
        (dest_dir / "COPYING").unlink()

        for name in zf.namelist():
            if not name.startswith(ZIP_RELEASE_PREFIX) or name.endswith("/"):
                continue
            rel = name[len(ZIP_RELEASE_PREFIX) :]
            target = dest_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)

    (dest_dir / "NOTICE_DOSBOX-X.txt").write_text(NOTICE_TEXT, encoding="utf-8")
    # zh_darksun.conf is intentionally NOT written here -- this script's output
    # is cached and only re-run when the pinned DOSBox-X version changes, so a
    # conf baked in here would silently go stale whenever dosbox_darksun.conf.template
    # is edited. package_release.py's write_dosbox_conf() writes it fresh every
    # time instead.

    exe = dest_dir / "dosbox-x.exe"
    if not exe.exists():
        raise SystemExit(f"解壓後找不到 {exe}，DOSBox-X 發布檔的內部結構可能變了，需要更新 ZIP_RELEASE_PREFIX")
    print(f"[OK] 已解壓 DOSBox-X 到 {dest_dir}")


def main() -> None:
    zip_path = download_asset()
    extract_dosboxx(zip_path, RELEASE_DIR / "dosbox-x")


if __name__ == "__main__":
    main()
