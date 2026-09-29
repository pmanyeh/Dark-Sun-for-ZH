# 《浩劫殘陽》繁體中文化專案

這是 SSI 1993 年 DOS 遊戲 *Dark Sun: Shattered Lands*（《浩劫殘陽：破碎大地》）的繁體中文化與逆向工程專案。
原版引擎只能顯示英文；本專案在不改變畫面模式、不散布原版遊戲檔案的前提下，
讓遊戲以原解析度顯示中文，並把對話、介面、圖片文字全部中文化。

> [!IMPORTANT]
> 本專案已接近完成，目前是公測階段（整合包 v0.9.0）；repository 不提供可直接遊玩的遊戲下載。
> 玩家必須自行合法持有原版遊戲；repository 不包含 Steam 原始遊戲檔、DOSBox-X
> 執行檔或字型檔。

## 專案特點

- **不散布原版檔案**：發布的整合包只含二進位差異補丁，在玩家本機套用到自己的 Steam 版上，
  安裝前後都逐位元組驗證，也能解除安裝還原成原版。
- **原解析度中文顯示**：不改畫面模式，在原版字型資源 FONT-100 後面附加一段 16 位元核心程式，
  於執行期載入 10×10 點陣中文字形；英文介面的排版與原版美術都保留。
- **中文穿過英文引擎**：每個中文字編碼成三個可列印的 ASCII 字元（Base94，`^xy`），
  能原封不動地通過引擎原有的字串處理、換行與存檔，只在畫面繪製時解碼。
- **對話腳本重新編譯**：GPL／MAS 對話腳本可做可變長度修改，並自動重定位所有跳躍、觸發器與外部入口；
  非目標 chunk 必須逐位元組相同才允許建置。
- **安全的 EXE 修補**：每一處修補都先比對原始 bytes，並拒絕碰到 MZ 或 Borland overlay 重定位的位置；
  修補範圍以外的 bytes 保證不變。
- **數位典藏原則**：新功能只新增、不取代。手冊上的原版熱鍵與 `-k911` 開發者除錯模式的行為全部保留，
  避免玩家誤以為「這個版本改壞了」。
- **名詞一致**：專有名詞一律依智冠當年的中文手冊定名，
  統一整理在 [`docs/名詞權威對照表.md`](docs/名詞權威對照表.md)，並有全資源一致性檢查工具。
- **舊存檔可沿用**：提供存檔修補工具，把存檔裡的全域字串與生物名字轉成中文。
- **可重現、可驗證**：從原版檔案到可玩組合包的每一步都有指令與自動驗證，目前共 266 項測試。

## 功能一覽

### 中文化內容

- **對話**：13,295 / 13,295 個翻譯單元（100%），包括是非選單、對話選單標題與拼接用的短片段。
- **介面**：背包、VIEW CHARACTER、創角畫面、雙職業畫面、頭像選單、遊戲選單、提示列、
  離開與讀取／存檔對話框、訊息框、USE 畫面與施法訊息、裝備欄與按鈕文字。
- **資料**：物品名稱與材質字首、法術／靈能名稱與說明卡、戰鬥資訊卡與 70 種效果名稱、
  觀察卡與物品卡、生物／NPC 名字。
- **圖片**：片頭兩張羊皮紙與片尾兩首詩，以原畫面的墨色漸層重新繪製中文，並保持原動畫格式。

### 操作改良（原版沒有的新功能）

- **遊標模式熱鍵**：`Z` 攻擊、`X` 觀察、`D` 行走（都是原版沒用到的鍵）。
- **智慧遊標**：
  - 用行走遊標點 NPC、門、箱子，相鄰就互動；不相鄰就自動走過去，到了再互動。按住 Ctrl 只移動。
  - 滑到可互動的物件上，遊標會換成觀察圖示。
  - 走不過去的物件（例如牆上的排水口、凹室裡的輪子）改用觀察遊標的規則直接查看。
  - 攻擊遊標點搆不到的目標，會先走到近戰距離再攻擊。
- **除錯模式的地圖傳送**：用 `-k911` 啟動時，按 `O` 開俯瞰地圖，按住 Shift 點地圖，全隊傳送過去。
- **停用中文輸入法**：DOSBox-X 啟動時停用 Windows 輸入法，避免熱鍵被注音輸入法吃掉。
- 玩家用說明見 [`docs/新操作說明.md`](docs/新操作說明.md)。

## 開發歷程

| 期間 | 階段 | 主要成果 | 紀錄 |
| --- | --- | --- | --- |
| 2026-08-13～08-17 | 奠基 | 以 OpenDS 抽取對話並建立統一本地化目錄；在 FONT-100 驗證中文字形顯示；建立 CJK 字庫 bank、Base94 傳輸與 GPL 對話重新編譯；鬥獸場開場對話完成實機回歸（v26） | re_01～re_45 |
| 2026-08-18～09-10 | 物品文字 | 物品說明與物品列的中文繪製，經歷多次失敗與回退後，改用字型資源內的核心程式 | re_46～re_53 |
| 2026-09-11～09-18 | 介面核心 | 釐清 overlay 重定位與共用的名稱繪製位置，建立 FONT-100 核心；背包與 VIEW CHARACTER 原解析度中文化。另有一條高解析度文字的實驗支線 | re_54～re_95 |
| 2026-09-20～09-23 | 對話完整化 | 修正對話選單行距、加入四選項換頁並消除殘影；從原版 GPLDATA 一次編譯全部譯文（v86） | re_96～re_99 |
| 2026-09-24～09-27 | 全面中文化 | 選單標題與 EXE 字串、法術名稱、操作改良、創角畫面、戰鬥資訊卡、片頭羊皮紙與片尾詩、全資源名詞統一、生物名字；建立免安裝整合包 v0.9.0 | re_100～re_107 |
| 2026-09-29～09-30 | 公測回饋 | 除錯模式的地圖傳送；修正智慧遊標查看牆上物件的問題（v154～v158） | re_104 §19～§20 |

各版本的細節、建置命令與下一步請見 [`handoff.md`](handoff.md)。

## 目前狀態與待辦

截至 2026-09-30，最新建置為 v158；公測整合包 v0.9.0 以 v153 為基礎。

- 實機確認 v141～v146 的部分畫面（生物名字、觀察卡、物品卡等）。
- 少數剩餘英文字串（名稱欄的 INACTIVE CHARACTER 等），以及換行避頭點。
- 完整遊戲流程的校對與回歸測試；用整合包內附的 DOSBox-X 實際進遊戲；GOG 版的驗證。

## 技術架構

1. **抽取**：以 [OpenDS](https://github.com/VirInvictus/opends) 解析 GFF 資源與 GPL 腳本，
   把對話、法術說明、物品名稱與 EXE 字串整理成 UTF-8 翻譯目錄（`localization/catalog/`）。
2. **字庫**：從譯文收集用到的字，依 append-only 的 Unicode → CJK ID 對照表
   （`localization/cjk_mapping.json`）產生 CJB1 字庫 bank，每個 bank 256 字，最多 16 個。
3. **編譯**：譯文編成 Base94 後，寫回 `GPLDATA.GFF`（對話）、`RESOURCE.GFF`（法術說明、物品名稱、
   圖片、FONT-100 核心）、`SEGOBJEX.GFF`（生物名字）與 `DSUN.EXE`（介面字串與掛鉤）。
4. **顯示**：`DSUN.EXE` 裡不會解碼的繪製路徑，以小型跳板轉進 FONT-100 核心
   （`tools/cjk_name_slot_cache.asm`）；核心解碼 Base94、從字庫 bank 載入字形，再交回原版繪製程式。
5. **組合與發布**：`tools/build_cjk_display_staging.py` 在隔離副本上產生可玩的組合包；
   `tools/release/` 把它做成差異補丁整合包，流程見
   [`docs/workflows/release-packaging.md`](docs/workflows/release-packaging.md)。

逆向工程的完整紀錄在 [`docs/re/`](docs/re/)。

## 字型

- **中文點陣字**：[Fusion Pixel Font](https://github.com/TakWolf/fusion-pixel-font) 10px（SIL OFL 1.1）。
  請自行下載 `Fusion_Pixel_10px.ttf` 放在 `Fonts/`；建置時轉成 10×10 的 CJB1 字庫。
- **片頭羊皮紙與片尾詩**：Windows 內建的微軟正黑體粗體（`msjhbd.ttc`），只在建置時用來重繪圖片。
- 早期試驗用過倚天 16×15 字型，已不再使用；相關轉換程式碼只保留作為參考（`--eten-dir`）。

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
- Fusion Pixel Font 10px（建立中文字庫時需要，見上方「字型」）

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
