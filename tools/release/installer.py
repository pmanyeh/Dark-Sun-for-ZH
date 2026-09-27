#!/usr/bin/env python3
"""浩劫殘陽：破碎大地 繁體中文化 -- 安裝／解除安裝程式

只用標準函式庫，整合包內附的 python-embed/ 就能執行。本程式不包含、也不會
下載任何原版遊戲檔案。使用者先把自己合法取得的遊戲檔案（Steam 版
GAME\\DARKSUN 資料夾裡的全部檔案）放進本程式旁的 game_data\\，本程式會：

  1. 核對 DSUN.EXE、RESOURCE.GFF、GPLDATA.GFF、CINE.GFF、SEGOBJEX.GFF 的
     SHA-256，確認是支援的版本；不符就中止，不改任何檔案。
  2. 把這五個原檔備份到 game_data\\_zh_backup\\，再套用二進位差異補丁，
     逐檔核對結果。
  3. 放入中文字型檔 C0～C11。
  4. 如果 game_data\\ 裡有舊存檔（SAVE*.SAV、DARKRUN.GFF），先備份，再把
     存檔裡殘留的英文選單標題與生物名字換成中文。

用法（一般直接雙擊「安裝中文化.bat」即可）：
    python installer.py
    python installer.py --uninstall
    python installer.py --game-dir "D:\\其他位置\\game_data"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bspatch_apply import apply_patch  # noqa: E402
from darksun_saves import migrate_save  # noqa: E402

BACKUP_DIR_NAME = "_zh_backup"
INSTALL_RECORD = "zh_install_record.json"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_ci(directory: Path, name: str) -> Path | None:
    """DOS 時代的檔名大小寫不一定，用不分大小寫的方式找檔案。"""
    for path in directory.iterdir():
        if path.is_file() and path.name.lower() == name.lower():
            return path
    return None


def fail(message: str) -> None:
    print()
    print("[錯誤] " + message)
    raise SystemExit(1)


def locate_game(game_dir: Path) -> Path:
    """遊戲資料夾要是 game_data\\DARKSUN（和 Steam 版把 GAME 掛成 C: 再進 DARKSUN 一樣）。"""
    if not game_dir.is_dir():
        fail(f"找不到 {game_dir}。")
    darksun = game_dir / "DARKSUN"
    if darksun.is_dir() and find_ci(darksun, "DSUN.EXE"):
        return darksun
    if find_ci(game_dir, "DSUN.EXE"):
        fail(f"遊戲檔案直接放在 {game_dir} 裡了。請改成把整個 DARKSUN 資料夾放進 {game_dir}，"
             "也就是變成 game_data\\DARKSUN\\DSUN.EXE。")
    nested = game_dir / "GAME" / "DARKSUN"
    if nested.is_dir() and find_ci(nested, "DSUN.EXE"):
        fail(f"遊戲檔案放在 {nested} 裡了。請把其中的 DARKSUN 資料夾直接放進 {game_dir}。")
    fail(f"{game_dir} 裡沒有 DARKSUN\\DSUN.EXE。請把 Steam 版 GAME 資料夾裡的整個 DARKSUN 資料夾複製到這裡。")
    raise AssertionError


def identify(game: Path, manifest: dict) -> tuple[str, str]:
    """回傳 (版本, 狀態)，狀態為 original 或 installed。"""
    hashes = {}
    for name in next(iter(manifest["editions"].values())):
        path = find_ci(game, name)
        if path is None:
            fail(f"game_data 裡缺少 {name}。")
        hashes[name] = sha256_of(path)
    for edition, files in manifest["editions"].items():
        if all(hashes[name] == info["source_sha256"] for name, info in files.items()):
            return edition, "original"
        if all(hashes[name] == info["target_sha256"] for name, info in files.items()):
            return edition, "installed"
    unknown = [name for name in hashes
               if not any(hashes[name] in (files[name]["source_sha256"], files[name]["target_sha256"])
                          for files in manifest["editions"].values())]
    fail("這份遊戲檔案不是支援的版本（目前支援 Steam 英文版），或已經被其他工具修改過。\n"
         f"        無法辨識的檔案：{', '.join(unknown) or '版本混雜'}\n"
         "        本程式沒有改動任何檔案。")
    raise AssertionError


def migrate_saves(game: Path, backup: Path, migration: dict) -> list[dict]:
    saves = sorted(p for p in game.iterdir() if p.is_file() and p.name.upper().startswith("SAVE")
                   and p.suffix.upper() == ".SAV")
    darkrun = find_ci(game, "DARKRUN.GFF")
    if darkrun:
        saves.append(darkrun)
    records = []
    for path in saves:
        data = path.read_bytes()
        try:
            patched, gstr, names = migrate_save(data, migration)
        except (ValueError, IndexError) as exc:
            print(f"  略過 {path.name}：無法解析（{exc}）")
            continue
        if patched == data:
            continue
        (backup / "saves").mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup / "saves" / path.name)
        path.write_bytes(patched)
        records.append({"file": path.name, "migrated_sha256": hashlib.sha256(patched).hexdigest()})
        print(f"  {path.name}：選單標題 {len(gstr)} 處、生物名字 {names} 處改成中文")
    return records


def install(game: Path) -> None:
    manifest = json.loads((HERE / "release_manifest.json").read_text(encoding="utf-8"))
    migration = json.loads((HERE / "save_migration.json").read_text(encoding="utf-8"))
    edition, state = identify(game, manifest)
    if state == "installed":
        print("這份遊戲已經安裝過中文化了，不需要再安裝。")
        return
    print(f"辨識為：{edition} 版原版檔案，開始安裝中文化 {manifest['version']}……")
    backup = game / BACKUP_DIR_NAME
    files = manifest["editions"][edition]
    patched = {}
    for name, info in files.items():
        path = find_ci(game, name)
        original = path.read_bytes()
        result = apply_patch(original, (HERE / "patches" / info["patch"]).read_bytes())
        if hashlib.sha256(result).hexdigest() != info["target_sha256"]:
            fail(f"{name} 套用補丁後的結果不正確，已中止；沒有改動任何檔案。")
        patched[path] = result
    banks = {}
    for name, digest in manifest["font_banks"].items():
        source = HERE / "resources" / name
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            fail(f"整合包裡的字型檔 {name} 缺少或損毀，請重新下載整合包。沒有改動任何檔案。")
        banks[name] = source.read_bytes()
    # Everything is verified; only now does anything in game_data change.
    backup.mkdir(exist_ok=True)
    for path in patched:
        shutil.copy2(path, backup / path.name)
    for path, data in patched.items():
        path.write_bytes(data)
        print(f"  已更新 {path.name}")
    for name, data in banks.items():
        (game / name).write_bytes(data)
    print(f"  已放入中文字型檔 {len(manifest['font_banks'])} 個")
    saves = migrate_saves(game, backup, migration)
    record = {
        "version": manifest["version"],
        "edition": edition,
        "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "patched": [path.name for path in patched],
        "font_banks": list(manifest["font_banks"]),
        "saves": saves,
    }
    (game / INSTALL_RECORD).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("[完成] 中文化安裝完成，請雙擊「玩遊戲.bat」開始遊戲。")


def uninstall(game: Path) -> None:
    record_path = game / INSTALL_RECORD
    if not record_path.is_file():
        fail("找不到安裝紀錄，這份遊戲可能沒有安裝過中文化。")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    backup = game / BACKUP_DIR_NAME
    for name in record["patched"]:
        shutil.copy2(backup / name, game / name)
        print(f"  已還原 {name}")
    for name in record["font_banks"]:
        path = game / name
        if path.is_file():
            path.unlink()
    for save in record["saves"]:
        path = game / save["file"]
        if path.is_file() and sha256_of(path) == save["migrated_sha256"]:
            shutil.copy2(backup / "saves" / save["file"], path)
            print(f"  已還原存檔 {save['file']}")
        else:
            print(f"  {save['file']} 在安裝後又存過檔，保留現狀（原本的備份在 {BACKUP_DIR_NAME}\\saves）")
    record_path.unlink()
    print()
    print("[完成] 已還原成英文原版。")


def main() -> int:
    parser = argparse.ArgumentParser(description="浩劫殘陽：破碎大地 繁體中文化 安裝程式")
    parser.add_argument("--game-dir", type=Path, default=HERE / "game_data")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    game = locate_game(args.game_dir)
    if args.uninstall:
        uninstall(game)
    else:
        install(game)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
