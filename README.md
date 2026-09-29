# 《浩劫殘陽》繁體中文化專案

這是 *Dark Sun: Shattered Lands*（《浩劫殘陽》）的繁體中文化與逆向工程專案。
專案目標是在不散布原始商業遊戲檔案的前提下，建立可重現、可驗證的文字抽取、翻譯、
中文字型顯示與遊戲資源重封裝流程。

> [!IMPORTANT]
> 本專案仍在開發中，目前是公測階段，還不是最終成品；repository 也不提供可直接遊玩的遊戲下載。
> 使用者必須自行合法持有原版遊戲；repository 不包含 Steam 原始遊戲檔、DOSBox-X
> 執行檔或專有字型媒體。

## 目前進度

截至 2026-09-30，最新建置為 v158；公測整合包 v0.9.0 以 v153 為基礎。

- **翻譯**：全部對話 13,295 / 13,295 單元（100%），包括是非選單、對話選單標題與漏抽的短片段。
  專有名詞依智冠手冊定名，統一整理在 [`docs/名詞權威對照表.md`](docs/名詞權威對照表.md)。
- **已中文化的畫面**：
  - 對話框與對話選項、物品名稱與材質字首、法術／靈能名稱與說明（`SPIN`）。
  - 背包、VIEW CHARACTER、創角畫面、雙職業畫面、頭像選單。
  - 戰鬥資訊卡與效果名稱、觀察卡與物品卡、生物／NPC 名字。
  - 遊戲選單、提示列、離開與讀取／存檔對話框、訊息框、USE 畫面與施法訊息。
  - 片頭兩張羊皮紙與片尾兩首詩（重畫圖片）。
- **操作改良**（只新增，原版按鍵與 `-k911` 除錯模式的行為都保留）：
  - 遊標模式熱鍵：`Z` 攻擊、`X` 觀察、`D` 行走。
  - 智慧遊標：用行走遊標點物件，相鄰就互動，不相鄰就走過去再互動；走不過去的物件
    （例如牆上的排水口、凹室裡的輪子）改照觀察遊標的規則直接查看。
  - 除錯模式（`-k911`）的地圖傳送：按 `O` 開俯瞰地圖，按住 Shift 點地圖，全隊傳送過去。
  - 玩家用說明見 [`docs/新操作說明.md`](docs/新操作說明.md)。
- **發布**：可建立免安裝的整合包（安裝時逐位元組驗證、可解除安裝還原），流程見
  [`docs/workflows/release-packaging.md`](docs/workflows/release-packaging.md)。GOG 版尚未驗證。
- 建置流程一律在隔離的 staging 副本上運作，不會修改 Steam 原始安裝。

目前仍待完成的主要工作：

- 實機確認 v141～v146 的部分畫面（生物名字、觀察卡、物品卡等）。
- 少數剩餘英文字串（名稱欄的 INACTIVE CHARACTER 等），以及換行避頭點。
- 完整遊戲流程的校對與回歸測試；用整合包內附的 DOSBox-X 實際進遊戲。

各版本的細節、建置命令與下一步請見 [`handoff.md`](handoff.md)，逆向工程紀錄在
[`docs/re/`](docs/re/)。

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

大部分 Python 工具只使用標準函式庫；執行測試需要 `pytest`，片頭／片尾圖片重畫需要 Pillow。

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
python -m pytest tests -q
```

目前共 266 項測試。部分測試需要本機的原版遊戲檔或 GNU 工具鏈，缺少時會自動略過。

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
