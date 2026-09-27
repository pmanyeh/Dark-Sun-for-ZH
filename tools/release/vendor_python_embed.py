"""Developer-side tool: bundle the official "embeddable" Python distribution
into the release package, so end users can run installer.py without having
Python installed themselves.

Like DOSBox-X, this is an unmodified, sha256-verified official binary from
python.org (PSF License, unrelated to the original game's copyright), staged
into dist/release_v100_zh/python-embed/. The pinned build already includes
_bz2/_hashlib/etc, which is everything installer.py + bspatch_apply.py need
(both are stdlib-only -- see bspatch_apply.py's docstring).

Usage:
    python tools/release/vendor_python_embed.py
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

PYTHON_VERSION = "3.12.10"
ASSET_NAME = f"python-{PYTHON_VERSION}-embed-amd64.zip"
ASSET_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{ASSET_NAME}"
# Cross-checked against the official .spdx.json checksum metadata for this file.
ASSET_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"


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
    urllib.request.urlretrieve(ASSET_URL, tmp)  # noqa: S310 -- pinned https python.org URL

    actual_hash = sha256_of_file(tmp)
    if actual_hash != ASSET_SHA256:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"下載的檔案雜湊值不符，拒絕使用：\n  預期 {ASSET_SHA256}\n  實際 {actual_hash}")
    tmp.replace(cached)
    print(f"[OK] 下載並驗證完成：{cached}")
    return cached


def extract_python_embed(zip_path: Path, dest_dir: Path) -> None:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)

    exe = dest_dir / "python.exe"
    if not exe.exists():
        raise SystemExit(f"解壓後找不到 {exe}，embeddable 發布檔的內部結構可能變了")
    shutil.copy2(dest_dir / "LICENSE.txt", dest_dir / "LICENSE_python.txt")
    print(f"[OK] 已解壓內嵌版 Python {PYTHON_VERSION} 到 {dest_dir}")


def main() -> None:
    zip_path = download_asset()
    extract_python_embed(zip_path, RELEASE_DIR / "python-embed")


if __name__ == "__main__":
    main()
