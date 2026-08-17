# 《浩劫殘陽》繁體中文化專案

這是 *Dark Sun: Shattered Lands*（《浩劫殘陽》）的繁體中文化與逆向工程專案。
專案目標是在不散布原始商業遊戲檔案的前提下，建立可重現、可驗證的文字抽取、翻譯、
中文字型顯示與遊戲資源重封裝流程。

> [!IMPORTANT]
> 本專案仍在開發中，目前不是完整漢化成品，也不是可直接遊玩的遊戲下載。
> 使用者必須自行合法持有原版遊戲；repository 不包含 Steam 原始遊戲檔、DOSBox-X
> 執行檔或專有字型媒體。

## 目前進度

截至 2026-08-16，專案已完成一個通過實機回歸的繁中顯示 checkpoint（v26）：

- 建立 10×10 中文字形顯示與多字庫 bank 載入機制，同時保留 9-row UI 配置。
- 建立 UTF-8 翻譯目錄到 Base94 runtime transport 的可重現編譯流程。
- 可安全抽取、修改、重組譯並回封 `GPL`／`MAS` 對話腳本。
- 可編譯 `SPIN` 法術說明與固定寬度 `NAME-1` 物件名稱。
- 支援 GPL 分支、同 chunk trigger、外部入口 ABI 與 `GPLI-1` 事件位址的重定位驗證。
- 已實機確認鬥獸場囚犯對話、出口 Yes/No、場景轉移、戰鬥觸發與中文對話行距。
- 建置流程以隔離的 staging 副本運作，不會直接修改 Steam 原始安裝。

目前仍待完成的主要工作：

- 修正物件說明、裝備欄與物品列的 Base94 中文 renderer。
- UI 文字中文化。
- 多選項對話的選項文字中文化。
- 擴充翻譯覆蓋率並進行完整遊戲流程校對與回歸測試。

最新的正式 checkpoint 與後續工作順序請見
[`docs/re/HANDOFF_NEXT_SESSION_2026-08-16.md`](docs/re/HANDOFF_NEXT_SESSION_2026-08-16.md)，
技術驗證摘要則見
[`docs/re/re_45_v26_gpli_event_relocation_official_checkpoint.md`](docs/re/re_45_v26_gpli_event_relocation_official_checkpoint.md)。

## Repository 內容

| 路徑 | 用途 |
| --- | --- |
| `localization/catalog/` | 對話位置、唯一翻譯單元與整合後的本地化目錄 |
| `localization/cjk_mapping.json` | append-only Unicode → CJK ID 對照表 |
| `localization/` | 翻譯資料、專有名詞表及分析產物 |
| `tools/` | 抽取、分析、編譯、驗證與 staging 建置工具 |
| `tests/` | Python 單元測試 |
| `docs/re/` | GPL、GFF、字型 renderer 與 DOS runtime 的逆向工程紀錄 |
| `vendor/opends/` | [OpenDS](https://github.com/VirInvictus/opends) Git submodule |

`scratch_test/`、`from Steam/`、`Fonts/` 與本機建置輸出皆由 Git 忽略，不會提交至
repository。

## 環境需求

- Windows 與 PowerShell
- Python 3.10 以上版本
- [Rust toolchain](https://www.rust-lang.org/tools/install)（用於編譯 OpenDS 工具）
- 自行合法取得的 *Dark Sun: Shattered Lands* 遊戲檔案
- DOSBox-X（僅在建立及執行可玩 staging 時需要）
- 合法取得的 ETEN 16×15 字型檔（建立正式來源字庫時才需要，不包含於本專案）

大部分 Python 工具只使用標準函式庫；單元測試不需要安裝 `pytest`。

## 開始使用

### 1. Clone repository 與 submodule

```powershell
git clone --recurse-submodules https://github.com/pmanyeh/Dark-Sun-for-ZH.git
Set-Location Dark-Sun-for-ZH
```

如果已經 clone 過但尚未取得 OpenDS：

```powershell
git submodule update --init --recursive
```

### 2. 放置自己的原版遊戲

現有工具的預設 Steam 遊戲目錄為：

```text
from Steam/games/Dark Sun-ENG/GAME/DARKSUN/
```

請將自己的原版檔案放在這個本機目錄，或在執行工具時透過 `--source`／`--game-dir`
指定其他位置。`from Steam/` 已列入 `.gitignore`；請勿強制加入 Git。

### 3. 編譯 OpenDS 工具

```powershell
cargo build --release --manifest-path vendor/opends/Cargo.toml
```

完成後，主要工具會位於 `vendor/opends/target/release/`，包含 `gff-cat`、`gpl-disasm`
與 `gpl-asm`。

### 4. 執行測試

```powershell
python -m unittest discover -s tests -v
```

### 5. 查看本地化管線

翻譯目錄、CJK 字庫、SPIN 回封、GPL 對話編譯及 staging 建置的完整命令與安全驗證，
請參考 [`localization/catalog/README.md`](localization/catalog/README.md)。例如，更新翻譯後的
字形 inventory：

```powershell
python tools/cjk_localization_pipeline.py inventory
```

重新抽取 OpenDS 對話資料可執行：

```powershell
.\tools\extract_opends_dialog.ps1
```

產生的商業遊戲文本 extract 會留在 ignored 本機檔案中，不會被 Git 追蹤。

## 翻譯與開發注意事項

- `localization/catalog/dialogue_units.csv` 是對話翻譯的主要 worksheet。
- `localization/catalog/localization_manifest.csv` 整合對話、GFF 資源與 EXE 候選文字。
- `localization/cjk_mapping.json` 的既有 ID 不可重新編號；新增字元時應使用 inventory 工具。
- Base94 transport 將 `^` 保留為控制前綴，翻譯文字不可直接包含該字元。
- GPL 可變長度修改必須通過重組譯、instruction alignment、位址重定位與非目標 chunk
  byte-identical 驗證。
- 不要直接修改原版 `DSUN.EXE`、`RESOURCE.GFF` 或 `GPLDATA.GFF`；一律在隔離 staging
  或暫存副本上操作。
- `docs/re/re_01` 至 `re_06` 保留早期研究過程，其中部分推測已被後續實證推翻；進行新工作時
  應優先閱讀最新 handoff 與較新的研究紀錄。

## 法律與版權聲明

本專案是非官方、由社群進行的相容性研究與繁體中文化工程，與原遊戲的開發商、發行商
及權利人沒有隸屬或背書關係。遊戲名稱、商標、程式、資料與原文內容的權利均屬其各自
權利人所有。

本 repository 不提供原版遊戲、由原版遊戲重建出的可玩安裝、專有字型，或其他需要另行
取得授權的媒體。請只對自己合法持有的遊戲副本使用本專案工具，也不要提交
`from Steam/`、`Fonts/` 或任何由商業遊戲直接抽出的未授權檔案。

第三方 submodule `vendor/opends/` 依其自身授權條款提供。本專案目前尚未加入 repository
層級的 `LICENSE`；在授權條款確立前，請勿假定未明示的再散布權利。
