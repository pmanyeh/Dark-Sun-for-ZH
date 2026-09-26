# 《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands) 繁中化交接指南 (handoff.md)

> **更新時間**：2026-09-26（v139～v140 片頭兩張羊皮紙中文化完成）
> **用途**：新 Session 的 AI 助手先讀這份文件，就能接手工作。依序讀第 0、1 節，其餘各節需要時再查。

---

## 0. 現況

- **最新版本**：`scratch_test/cjk_display_staging_v140_intro_scrolls_fixed`（2026-09-26）：v138 ＋ 片頭兩張羊皮紙中文化
  （CINE.GFF `BMA 8`／`BMA 9`，`--intro-scrolls`，re_107），已實機確認（使用者 2026-09-26）。
  v139 會在第一張羊皮紙後當掉（影格 0 變長），可以刪掉。
- v138：v136 ＋ BUTN 按鈕文字（丟棄／拆分／更多／賣出／資訊／離開，
  `creation_icon_layer.build_button_texts`；標籤是 BUTN chunk 第 109 byte 的長度＋文字）。v137 實測會解碼但置中偏左；
  v138 讓按鈕排版（常駐 `0x2F8C0`）改用會解碼的寬度函式（`2847:00ED` 改成 tag `FF8E` 入口），已實機確認（使用者 2026-09-26）。
- v136：v135 ＋ 背包底部標籤（裝備欄名稱、空位、箱子／袋子／商店），
  **v136 還沒實機測試**。v135 已實機確認。
- v135：v134 ＋ 其餘提示列文字（遊戲選單圖示 `DS:0C4A` 表、USE 畫面提示、
  領隊／電腦控制句子、CURRENT STATUS），**v135 還沒實機測試**。
- v134：v133 ＋ 底部提示列（`DS:3272`，9 條）、離開對話框按鈕（存檔／離開／取消）、
  頭像右鍵選單的新建／加入／取消、VIEW CHARACTER 三位數 HP 不再蓋住「生命:」。**v134 還沒實機測試**。
  - v133：遊戲選單說明、音樂開關、離開遊戲問句已實機確認；商店訊息還沒遇到商店。
  - v132：v129 ＋ 戰鬥資訊卡中文化（re_106）。
  v130／v131 實測出現「移?」，v132 修正格式字串的 `%`（re_106 §4），已實機確認（使用者 2026-09-26）。
  - v129 = v127（創角畫面）＋ NAME 列上移 3px ＋ 職業清單 ◆ 對齊，全部已實機確認（使用者 2026-09-26）。
  - v122～v128 是這波創角工作的中間版本，可以刪掉。
  - 組合包裡另有 `launch-debug-k911.cmd`，會用 `-k911` 啟動除錯模式。
- **專案原則（使用者 2026-09-26 決定）**：數位典藏。新功能只能加上去，原版按鍵與行為（含 `-k911` 除錯模式）不可改。
  改任何輸入或行為之前，先對照手冊（`HotKey_in_Game.txt`）與原版 EXE（re_104 §18）。
- **翻譯進度**：對話單元 13,295 / 13,295（100%）。現在的工作重點是把程式裡的字串顯示成中文，以及改良操作。
- **已中文化**：
  - 全部對話（re_99），包括漏抽的短片段和是非選單（re_103）。
  - 對話選單標題（re_103）。
  - 背包／VIEW CHARACTER 的標籤、性別、種族、陣營、職業（re_100、re_102）。
  - 物品名稱（NAME-1）與材質字首（re_100、re_101）。
  - EXE 內的訊息框、存讀檔提示、戰鬥彈出框、法術／靈能名稱、頭像狀態、USE 按鈕（re_103）。
  - 學法術卷軸下方的兩行文字（v118～v120，re_104 §16）。
  - 創角畫面（CREATE CHARACTERS → NEW）左下的資料區：屬性、性別種族、陣營、職業、防禦，並新增生命／靈能標籤（v123，re_105）。
  - 創角畫面右側的職業清單、靈能分類、神術領域與切換鈕（ICON 圖片重畫，v127，re_105 §6）。
  - 戰鬥右上角資訊卡：狀態（正常／70 種效果名稱）、「移動:%d」，並重新排版（v130，re_106）。
  - 遊戲選單、提示列、離開對話框、頭像選單、裝備欄、背包按鈕文字（v133～v138）。
  - 片頭兩張羊皮紙（圖片重畫，微軟正黑體粗體反鋸齒，v140，re_107）。
- **操作改良（v107～v117，re_104）**：
  - 遊標模式熱鍵（v121 起）：`Z`＝攻擊、`X`＝觀察、`D`＝行走。原版的 `A`（動畫開關）、空白鍵、除錯鍵都已還原。
  - 智慧遊標（非戰鬥時）：
    - 行走遊標點物件（NPC、門、箱子，不含隊員）：相鄰就互動；不相鄰就走過去，走到之後自動互動。
    - 按住 Ctrl 點：只移動，不互動。
    - 觀察遊標點太遠或視線被擋的東西：走過去，走到之後自動互動（戰鬥中維持原版訊息）。
    - 靜態物件（石棺、草堆）會走到旁邊的空格。
    - 懸停在可互動的物件上時，行走遊標會換成觀察圖示。
    - 攻擊遊標點搆不到的目標（沒有遠程手段）：走過去再攻擊。遠程攻擊照原版。
    - 從觀察／攻擊遊標開始「走過去」時，會先切回行走模式（非行走模式下世界是暫停的）。
  - 建置選項：`--cursor-hotkeys`、`--smart-cursor`（都需要 `--view-ui`；`--cursor-hotkeys` 另外需要 `--smart-cursor`）。
  - 玩家用的說明：`docs/新操作說明.md`。建置時如果有上述任一選項，
    會轉成純文字檔 `新操作說明.txt`（UTF-8 含 BOM），放在組合包根目錄。
- 各版本的細節：v90～v106 見 re_103（含附錄的逐版紀錄），v107～v120 見 re_104。

---

## 1. 下一步（依優先順序）

### 1.0 剛完成：片頭兩張羊皮紙（v139～v140，re_107）

- 第一張（The once lush…）是 CINE.GFF `BMA 8` 影格 0，要在標題畫面不按鍵、等很久才會出現；第二張（By order of…）是 `BMA 9` 影格 0，START GAME 後出現。
- 英文字只用一個色號；擦掉後用微軟正黑體粗體 20px 重寫，邊緣用羊皮紙本身的「墨色→紙色」漸層做反鋸齒。
- 顏色要用**執行期調色盤**（緩衝區 `490F:0000`），CINE 的 PAL chunk 只有片段（re_107 §2）。
- **教訓**：v139 的影格 0 變長，後面的動畫影格全部移位，第一張之後就當掉。
  v140 改用最短 RLE 並補零到原長度，整個 BMA 除了影格 0 都逐位元組不變（re_107 §4）。
- 上一波的創角畫面（v122～v129）細節見 re_105；使用者常問的「遊俠選不到」是原版規則，見 re_105 §7。

### 1.1 下次開遊戲先確認

- v133：遊戲選單圖示的說明文字、音樂開關訊息、離開遊戲的兩個問句、戰鬥中存檔的訊息。
  商店的「商店／不成交!／成交!／錢不夠」走 `0578:0070`，**繪製路徑沒追到**，若出現亂碼要在商店開著時追 stub（re_106 附近的做法：執行期掃 `cd 3f 00 00` 表頭）。
- 戰鬥資訊卡：HP 三位數時與「移動」是否太擠、身上有法術效果時的名稱（譯名在 `localization/catalog/exe_effect_names.csv`）。
- 戰鬥中的 `Z`／`X`／`D`（v121 起的遊標熱鍵，還沒在戰鬥中測過）。

### 1.2 剩餘英文的處理順序

- **使用者決定不翻（2026-09-26）**：難度名稱（EASY…HIDEOUS）、圖片按鈕（存讀檔的 SAVE／EXIT／DELETE、創角 DONE、職業小圖 17101～17108）、
  主選單火焰藝術字。維持英文當原版美術。
- **片頭**：兩張羊皮紙已完成（v140）。工作人員名單、SSI、AD&D、公司標誌都**不翻**（使用者 2026-09-26 決定）。
- **下一步：片尾的兩首詩**（CINE.GFF `BMP 10`／`BMP 11`），做法照 re_107 §6；「龍之剋星」這個譯名使用者已同意。
- 已完成：遊戲選單、商店（未實測）、提示列、離開對話框、頭像選單、裝備欄、背包按鈕文字（v133～v138）。
- 創角與 VIEW CHARACTER 的 `NAME:`、`EXP`、`DAM` 仍是英文。
- 剩下的零星字串：`INACTIVE CHARACTER`（`1AC1`，VIEW 名稱欄那份）、`LOAD` 等，遇到再處理。

### 1.2.1 WIND／ICON 按鈕的技術筆記

以前卡在「不知道 WIND 格式」，這波創角工作已經把需要的格式都查清楚了，建議從這裡接續：

- WIND 的子元件記錄是 `"BUTN"`／`"EBOX"` + ID(4) + x(2) + y(2)，只存左上角（re_105 §4）。
- 按鈕上的英文字通常是**與按鈕同 ID 的 ICON 圖片**（re_105 §6.1）。先用 `gff-cat list` 找同 ID 的 ICON，
  再用 `creation_icon_layer.decode_icon` 看內容；按鈕的點擊大小就是 ICON 大小。
- 重畫中文 ICON 可以直接沿用 `creation_icon_layer.chinese_icon`（保留每格顏色，左邊至少留 8px）。
  ICON 長度改變時，建置驗證要允許 `GFFI-2` 變動（`build_cjk_display_staging.py` 已處理創角的情況）。
- v98 已把 EXE 唯一的 EXIT 改成「離開」，但卷軸上仍是英文，所以卷軸的 EXIT 應該是 ICON。

### 1.3 尚未盤點的 EXE 字串

- 遊戲選單（GAME MENU、MUSIC ON…）、商店（STORE、NO DEAL!、SOLD!）、
  背包下方提示列（`SELECT K'RATCHEK`、`HIT POINTS: CURRENT/MAX`）。
- 每一條都要先確認繪製路徑：
  - 會解碼的路徑：直接加進 `exe_text_layer`。
  - 經過 `191F:0A40` 或 `0580:005C` 的：已經會解碼。
  - 其他不解碼的：用 FONT 核心 tag redirect，做法見 re_103 §6。
- 起手式：
  1. 請使用者提供想先處理的畫面截圖或字串。
  2. 找出引用字串的程式碼（搜尋 `push <DGROUP偏移>` 等立即值），判斷繪製路徑，
     評估「原地放得下嗎？」、「路徑會解碼嗎？」。
  3. 如果大量字串都走 `339E:016D`，就研究在 formatter 加一個**窄範圍**的 Base94 解碼。
     先讀 re_52、re_53、re_63，了解當年失敗的原因，並同時處理 7px 固定前進量的問題（見 3.3）。

### 1.4 暫緩的字串

- `INACTIVE CHARACTER`（`1AC1`）和第二個 `CANCEL`（`1B7F`）：其他路徑也在用。
- `LOAD`（5 bytes）原位放不下，`NEW`／`ADD` 也還沒處理。

### 1.5 學法術卷軸左下角「第?級」顏色偏淡

- 使用者說應該是深色，決定之後再處理（re_104 §16）。目前的線索：
  - 中英文字形的像素值相同（`FEh`／`14h`），所以不是字形造成的。
  - 開啟卷軸時如果等級是 1，會呼叫 `0140:071A(視窗, 4394, 1)` 設定按鈕狀態。
  - USE 畫面的同類按鈕顏色正常。建議用 `from Steam` 原版比對 `LEVEL 1` 的顏色。

### 1.6 其他

- **避頭點**：換行偶爾會讓「，」「。」出現在行首。
- 右側直排的 `MORE` 是圖片，使用者說先不處理。

---

## 2. 重建與交付（`scratch_test/` 在 `.gitignore` 裡）

```bash
# 1) mapping（已 commit；只有新增字元時才重跑，三個 catalog 都要給）
python tools/cjk_localization_pipeline.py inventory \
  --catalog localization/catalog/localization_manifest.csv \
  --catalog localization/catalog/fixed_ui_labels.csv \
  --catalog localization/catalog/exe_spell_names.csv

# 2) 字型 bank（mapping 有新字時才重建）
python tools/cjk_localization_pipeline.py build-banks --mapping localization/cjk_mapping.json \
  --output scratch_test/formal_cjk_fusion_10x10_v22_spell_names --font Fonts/Fusion_Pixel_10px.ttf \
  --font-size 10 --pixel-width 10 --height 10 --advance 10 --threshold 64 --fit-mode pixel-aligned

# 3) 對話封包 → 疊上 NAME-1
python tools/compile_gpl_dialogue_patch.py \
  --all-translated \
  --fragment-overrides localization/catalog/dialogue_fragment_overrides.json \
  --translate-menu-titles \
  --output scratch_test/gpl_full_from_pristine_v10_spell_mapping
python tools/compile_gff_name_records.py \
  --prior-package scratch_test/gpl_full_from_pristine_v10_spell_mapping/gpl-dialogue-patch.json \
  --output scratch_test/gpl_full_v10_name_records

# 4) 組合包
python tools/build_cjk_display_staging.py \
  --mapping localization/cjk_mapping.json \
  --bank-package scratch_test/formal_cjk_fusion_10x10_v22_spell_names/cjk-bank-set.json \
  --spin-package scratch_test/spin_gff_import_title_newline_v4_glossary/gff-text-replacements.json \
  --gpl-package scratch_test/gpl_full_v10_name_records/gpl-dialogue-patch.json \
  --ebox-line-gap 2 --menu-line-gap 2 --dialogue-option-pitch 11 --view-ui \
  --cursor-hotkeys --smart-cursor --intro-scrolls \
  --output scratch_test/cjk_display_staging_vNN_xxx
```

- **存檔**：建好後，從**使用者最後玩的那一版**複製**全部**存檔：`SAVE*.SAV`（使用者會存到第 10 格以上）、
  `DARKRUN.GFF`、`CHARSAVE.GFF`。
  - v107～v116 只複製了 `SAVE0?.SAV` 和 `DARKRUN.GFF`，漏掉 v109 的 `SAVE10.SAV` 和 `CHARSAVE.GFF`，後來才補進 v117。
  - 存檔名稱另存在別的檔，所以讀檔清單上的名字會跟遊戲內不同，但 SAVE01 本身是同一份。
- **GSTR 修補**：全域字串 GSTR 會存進存檔，讀舊存檔時英文標題會被還原。
  - 字串表每格 42 bytes，依序是 GSTR[1] What do you say?、[2] END、[3] CLOSE、[4] What do you do?……
  - 複製存檔之後，執行 `python tools/patch_save_gstr.py <組合包>/GAME/DARKSUN scratch_test/gpl_full_from_pristine_v10_spell_mapping/gpl-dialogue-patch.json`
    （要給步驟 3 第一個指令的封包；疊上 NAME-1 的那一份格式不同，會出現 `KeyError: 'kind'`）：
    - 它會把 MAS-99 設定的 GSTR[1][4][5][6][7] 裡還是英文的改成中文。
    - 原檔備份為 `*.orig`。新開的遊戲不受影響。
- 只要對話封包改版，舊存檔記住的觸發器位址就可能失效（re_99）。
- **`--view-ui` 另外會替換的 RESOURCE.GFF 內容**（re_105）：WIND-3011／3012／3013 的按鈕位置，
  以及 18 張創角 ICON（2002～2009、2038～2047）。ICON 長度改變會連帶更新 `GFFI-2`，建置驗證已允許。
- **`--intro-scrolls`**：替換 CINE.GFF 的 `BMA 8`／`BMA 9`（片頭羊皮紙），驗證只有這兩個 chunk 不同。
  需要 Pillow 與系統字型 `C:/Windows/Fonts/msjhbd.ttc`（re_107 §5）。
- **測試**：`python -m pytest tests -q`，目前 250 項全過。
- **英文原版參考**：`scratch_test/english_reference` 是 Steam 英文版的副本（設定檔沿用組合包的），要對照原版畫面時用它，不要動 `from Steam`。

---

## 3. 技術事實與限制

### 3.1 位址換算

- 檔案位移 = `0x5400` + (執行期段 − `0x824`) × 16 + 偏移。
  - 例：`339E:016D` → `0x30D0D`；`4B7A:0000` → `0x48960`。
  - 舊文件（re_94）用的 `0xD640` 是錯的。
- overlay 程式裡 far call 的段值**不能**直接換算（例如 `0x140`→`2A1D`、`0x150`→`339E` 只是巧合）。
  要到執行期讀記憶體確認，查法見 re_103 §5。

### 3.2 字串從哪裡來

- 選單標題（`WHAT DO YOU SAY?` 等）不在 EXE，而是 GPLDATA 的 GSTR，已在 v91 處理（re_103 §2）。
- EXE 的畫面字串都在 DGROUP（檔案 `0x48960`，執行期段 `4B7A`）。
  - 用 regex `(?<=\x00)[\x20-\x7e]{4,}(?=\x00)` 掃描，再排除檔名、錯誤訊息等，約有 570 條。
  - GUI 錯誤訊息約 700 bytes，在 `38D7～3B97`，不在上面的 570 條裡。
  - `localization_manifest.json` 的 `exe_*` 單元混了大量雜訊（例如 `X?VCT?VC...`、`Borland C++`），不能直接當翻譯清單。

### 3.3 繪製路徑

- **大多數 UI 繪製路徑不會解碼 Base94**，翻譯每一條字串之前都要先確認路徑。
- 最通用的 formatter 是 `339E:016D`（`%C%s%d…`）：
  - `%s` 迴圈在 `339E:02E8`，檔案 `0x30BA0+0x2EB`，逐字呼叫 `11A4:59C1` 畫字。
  - v34／v35 曾經在這個迴圈加解碼，結果畫面空白或當機（re_52、re_53）。
    `build_cjk_display_staging.py` 目前會拒絕這兩個實驗旗標。
  - 前進量是固定的 `寬度('H')+1`，大約 7px（re_63），10px 寬的中文字會重疊 3px。
- 已經會解碼的路徑：EBOX（對話框）、對話選項、確認框按鈕（`2A1D:07FA`）、
  `191F:0A40`（v102 的 FF84）、`0580:005C` 訊息框（v97 的 FF82）、選單標題（v91 的 FF81）。
- 物品懸停列、右鍵資訊卡都不會解碼（re_101 §2）。
- FONT 核心的 tag redirect 會把中文解碼到 name-slot，**每次繪製最多 10 個相異中文字**（含全形標點）。

### 3.4 空間與長度

- 一個中文字編碼成 `^xy`，佔 3 bytes。DGROUP 的字串原地通常放不下（`GAME MENU` 9 bytes，「遊戲選單」12 bytes）。
- 字串可以搬走，再改引用它的立即值（`exe_text_layer` 會自動處理）。但 DGROUP 沒有現成的空地：
  - re_56 已證明 DGROUP 尾端不能用。
  - 可能的來源：`38D7～3B97` 的 GUI 錯誤訊息、`1FA5～1FDD` 的除錯字串。必須先證明沒有其他引用才能用。
  - 法術名稱區重新排列後還剩 432 bytes（v100）。
- 對話選項上限 49 bytes（2 個空白加最多 15 個中文字）。超過會丟 `MenuTextTooLong`。
- **格式字串**：中文的 Base94 編碼可能含 `%`（例如「動」＝`^"%`），經過 sprintf 會被當成格式符號。
  `exe_text_layer` 已自動把含 `%` 譯文裡的 `%` 寫成 `%%`；其他會進 sprintf 的新路徑也要比照（re_106 §4）。
- 訊息框每則最多 30 bytes。

### 3.5 字元碼已經用完

- name-slot 暫借了 10 個碼：`` " # & < > \ ~ ` _ | ``。
- 材質字首用了 6 個碼：`* @ [ ] { }`。
- 這 16 個字元只要出現在任何畫面文字裡，就會被畫成中文字形（re_101 §7 的「貝」就是 `<`）。
  所以譯文不能含這些字元。看到英文裡夾著莫名的中文字，先查它原本是不是其中之一。

### 3.6 修補規則

- 修補 overlay 區時，要用 `plan_name_slot_consumers.verify_overlay_relocations` 檢查，並確認沒碰到 MZ 重定位。
  `view_ui_layer.apply_view_ui_exe_patches` 是現成的範例。
- **會被引擎比對的字串不能翻**：`END`、`CLOSE`、`DEBUG`、玩家打字比對的關鍵字、`string compare` 的對象（re_99）。
  DGROUP 的 `CLOSE`（`1F11`）、`DEBUG`（`1F17`）就是其中之一。
- 是非選單要和 `ds:1F61 "answer yes or no"` 的比對結果一致（re_103 §3）。

### 3.7 已知風險（目前沒有症狀）

- 常駐字型快取 `2E86:545A～5533` 和 name-slot trampoline `2E86:5414`，都在計時器 ISR 的私有堆疊 `53B6～55A6` 裡。
  若出現隨機花字或當機，從這裡查。
- 訊息框的字形格和物品名稱共用，訊息顯示期間如果背包重畫，字形可能被換掉。

---

## 4. 操作注意

- **環境**：Windows（PowerShell），根目錄下直接用 `python`。JSON／Python 用 `utf-8`，CSV 用 `utf-8-sig`。
- **背景程序**：舊文件要求不要終止 `python scratch_test/run_bridge_injection.py`。
  目前不確定它是否仍在使用。如果看到它在跑，不要 kill，先問使用者。
- **DOSBox-X-AI**：
  - 一律用 PowerShell `Start-Process` 啟動（`-WorkingDirectory` 指到組合包根目錄）。
  - 重開之前，要等 9876 埠釋放。否則新執行個體的 bridge 綁定失敗，會整個停用，這時只能再重開一次。
  - 關掉使用者可能正在玩的執行個體之前，要先問。
- **組合包目錄被佔用**：DOSBox 開著組合包時，那個目錄刪不掉。重建時請換一個新的輸出目錄名。
- **滑鼠座標**：`move_mouse_absolute` 的 x 要用擷取畫面上的 x 乘 2（擷取寬 640，遊戲內容在左半），y 不變。
- **滑鼠操作**：
  - 只用 MCP 工具（`click_at`、`move_mouse_absolute`、`set_mouse_button`）操作滑鼠，不要用 Python 直連 bridge 送滑鼠指令。
  - 如果遊戲裡的游標完全不動，通常是使用者的實體滑鼠停在 DOSBox 視窗上。請使用者把滑鼠移開，不要重開 DOSBox。
  - 有些按鈕（例如創角畫面的屬性按鈕）對 `click_at` 的快速點擊沒反應，要用 `set_mouse_button` 分開送按下與放開。
  - 創角畫面的職業與元素是切換式：點已選的會取消，重選職業時 HP 會重擲。不要在使用者的角色上亂點。
- **截圖放大**：`capture_frame` 的畫面在左半、每列重複兩次。要量像素時，把左半 320×400 縮成 320×200 再放大檢視
  （這次用的腳本在工作階段的暫存目錄 `grab.py`，概念很簡單，可以照著重寫）。
- **快捷鍵**：主選單按 `L` → `Enter` 讀檔，按 `C` 進 CREATE CHARACTERS。`i` 開背包，`v` 開 VIEW CHARACTER，`1～4` 切換角色。
- **記憶體**：讀之前先 `pause_execution`；讀完記得 `continue_execution`。
- **Python 腳本**：寫在 Bash heredoc 裡時，`\x..` 會被轉成真的控制字元。請把腳本寫進暫存目錄的檔案再執行。
- **Unicorn 模擬測試**：同一位址改寫程式碼之後，Unicorn 會沿用舊的翻譯快取。每個 stub 要放在不同位址。

---

## 5. 修改譯文時的規範

- 譯名以 `docs/名詞權威對照表.md` 為準（智冠手冊定名）。
  - 法術／靈能名稱一律依詞彙表（使用者 2026-09-24 決定）。
  - Psionicist 維持「靈能師」（使用者 2026-09-24 決定），Thief 用「小偷」。
- 修改對話譯文時，以下 4 個檔案要同步更新：

  | 檔案路徑 | 格式 | 說明 |
  | :--- | :--- | :--- |
  | `localization/catalog/dialogue_units.json` | JSON (utf-8) | 對話單元主庫（含 summary 計數） |
  | `localization/catalog/dialogue_units.csv` | CSV (utf-8-sig) | 對話單元表格 |
  | `localization/catalog/localization_manifest.json` | JSON (utf-8) | 全遊戲在地化總清單（含 summary 計數） |
  | `localization/catalog/localization_manifest.csv` | CSV (utf-8-sig) | 全遊戲在地化總清單表格 |

- **空白對齊**：字串開頭與結尾的空白有排版或拼接意義，譯文必須和英文原文完全一致，寫入前要用腳本驗證。
  - 選項開頭通常有 2 個空白：`"  Yes, I agree."` → `"  是的，我同意。"`。
  - 句子拼接前半段通常有結尾空白：`"I saw him "` → `"我看見了他 "`。
  - 句子拼接後半段通常有開頭空白：`" in the city."` → `" 在城鎮裡。"`。
- 對話裡的短片段（3 字元以內）另外放在 `localization/catalog/dialogue_fragment_overrides.json`，
  以 chunk+offset 為鍵，空字串代表不印（re_103 §1）。

---

## 6. 相關文件

| 主題 | 文件 |
|---|---|
| 對話全量編譯、GPL 池、withheld | `docs/re/re_99_*` |
| 背包／VIEW CHARACTER 併入主線 | `docs/re/re_100_v87_view_ui_merge.md` |
| 材質字首、固定字元碼、天生攻擊括號 | `docs/re/re_101_v88_material_words.md` |
| 職業顏色、行距、位址換算更正 | `docs/re/re_102_v89_class_colour_and_view_rows.md` |
| 選單標題、漏抽片段、EXE 字串、FONT 核心 entry、overlay 段號查法；v90～v106 逐版紀錄（附錄） | `docs/re/re_103_v90_v106_menu_titles_and_exe_strings.md` |
| 遊標模式、熱鍵分派、左鍵分派、移動指令、智慧遊標、學法術卷軸、除錯模式 | `docs/re/re_104_cursor_mode_hotkeys_investigation.md` |
| 創角畫面版面表、WIND-3011 按鈕、共用繪製函式、overlay stub `4A41` | `docs/re/re_105_character_creation_layout_survey.md` |
| 戰鬥資訊卡、效果名稱表 | `docs/re/re_106_combat_info_card.md` |
| 片頭羊皮紙、CINE 影格格式、執行期調色盤、BMA 不能變長 | `docs/re/re_107_intro_scrolls.md` |
| 選單換頁／疊影 | `docs/re/re_96`～`re_98` |
| `%s` 迴圈解碼失敗紀錄 | `docs/re/re_52`、`re_53`、`re_63` |
| 玩家用操作說明 | `docs/新操作說明.md` |
| 名詞對照 | `docs/名詞權威對照表.md` |
