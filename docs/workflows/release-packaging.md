# 發布「免安裝整合包」流程

參考叛變克朗多中文化（`D:\git\betrayal-at-krondor-for-zh`）的做法。整合包**不含任何原版遊戲檔案**：
玩家把自己的 Steam 版 `GAME\DARKSUN` 整個資料夾放進 `game_data\`，執行「安裝中文化.bat」，
在本機用二進位差異補丁產生中文版。所有指令從 repo 根目錄執行。

## 整合包內容（`dist/darksun_zh_release_v<版本>/`）

| 項目 | 內容 |
|---|---|
| `安裝中文化.bat`／`解除中文化.bat`／`玩遊戲.bat` | CRLF；用內附的 Python 與 DOSBox-X，路徑一律明確寫出 |
| `installer.py`、`bspatch_apply.py`、`darksun_gff.py`、`darksun_saves.py` | 只用標準函式庫 |
| `patches/<版本>_<檔名>.bsdiff`、`release_manifest.json` | 5 個檔（DSUN.EXE、RESOURCE／GPLDATA／CINE／SEGOBJEX.GFF）的差異補丁與來源／成品雜湊 |
| `resources/C0～C11` | 中文字型檔（新檔案，直接複製） |
| `save_migration.json` | 舊存檔的 GSTR 標題與生物名字中文位元組（預先算好） |
| `dosbox-x/`、`python-embed/` | 官方固定版本（DOSBox-X 2026.08.02、Python 3.12.10），附授權檔 |
| `dosbox-x/zh_darksun.conf` | 硬體設定同 Steam 版（S3、32 MB、7000 cycles、SB16 220/5/1/5），加 `ime=false`；掛載 `..\game_data`、`cd DARKSUN`、`call DARKSUN.BAT` |
| `README_安裝說明.txt`、`新操作說明.txt`、`LICENSE_Fusion_Pixel_Font.txt` | UTF-8 BOM＋CRLF |
| `game_data/` | 只有一個說明檔 |

## 什麼時候要重跑

- **組合包換新版**（翻譯、EXE、資源有改）：改 `tools/release/release_config.py` 的 `STAGING`（與 `GPL_PACKAGE`），
  再跑 `build_release_patches.py` 和 `package_release.py`。
- **只改說明文件或啟動設定**（`tools/release/templates/`）：只跑 `package_release.py`。
- **升級 DOSBox-X／Python**：改 `vendor_dosboxx.py`／`vendor_python_embed.py` 的版本與雜湊常數。下載有快取（`dist/_vendor_cache/`）。
- **發布新版本號**：改 `release_config.py` 的 `RELEASE_VERSION`。

```powershell
python tools/release/build_release_patches.py   # 需要 pip install bsdiff4（只有開發端需要）
python tools/release/package_release.py
python -m pytest tests -q
```

`build_release_patches.py` 會用發布用的 `bspatch_apply.py` 把每個補丁套回原檔，必須和組合包逐位元組相同才寫出。
`package_release.py` 會拒絕和 `STAGING` 不符的補丁資料，並確認整合包裡沒有 `.SAV`／`.GFF`／`DSUN.EXE`。

## 安裝程式的保證

- 先用雜湊辨識版本（原版／已安裝／無法辨識）。無法辨識就中止，**不改任何檔案**。
- 5 個補丁的結果與全部字型檔都驗證通過後才開始寫入；原檔備份在 `game_data\DARKSUN\_zh_backup\`。
- 舊存檔（`SAVE*.SAV`、`DARKRUN.GFF`）先備份再修補；重跑不會重複修改。
- `--uninstall` 還原 5 個檔、移除字型檔；存檔只在安裝後沒再存過時才還原。

## 手動端到端測試（每次出包後）

1. 用 Windows 內建的解壓縮（檔案總管或 PowerShell `Expand-Archive`，**不要用 Git Bash 的 `unzip`**，它不認 UTF-8 旗標，中文檔名會變亂碼）把 zip 解壓到 `scratch_test/release_e2e/`，把 `from Steam/games/Dark Sun-ENG/GAME/DARKSUN` 整個資料夾複製進 `game_data\`。
2. 執行「安裝中文化.bat」，確認 5 個檔和 `STAGING` 的相同。
3. 執行「玩遊戲.bat」（官方 DOSBox-X，不是開發用的 DOSBox-X-AI），確認能進遊戲、中文正常、沒有設定值警告。
4. 執行「解除中文化.bat」，確認還原成 Steam 原檔。

## 版本支援

- Steam 英文版：已驗證。
- GOG 版（1.10）：依 `vendor/opends/docs/source-hashes/ds1-gog-1.10.toml`，會修改的 5 個檔與 Steam 版雜湊完全相同（整份只有 DARKRUN.GFF、DARKSUN.BAT、SOUND.BAT 不同），所以安裝程式直接認得，但沒有實機測試過。
  若將來出現檔案不同的版本，在 `SOURCE_EDITIONS` 加入它的原檔資料夾，重跑兩支腳本即可。
