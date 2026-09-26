# 《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands) 繁中化交接指南 (handoff.md)

> **更新時間**：2026-09-26（依 2026-09-25 的進度重整結構）
> **用途**：新 Session 的 AI 助手先讀這份文件，就能接手工作。依序讀第 0、1 節，其餘各節需要時再查。

---

## 0. 現況

- **最新版本**：`scratch_test/cjk_display_staging_v120_scroll_update_rect`（2026-09-25），使用者已實機確認。
  到 v120 為止都已 commit 並 push。
- **翻譯進度**：對話單元 13,295 / 13,295（100%）。現在的工作重點是把程式裡的字串顯示成中文，以及改良操作。
- **已中文化**：
  - 全部對話（re_99），包括漏抽的短片段和是非選單（re_103）。
  - 對話選單標題（re_103）。
  - 背包／VIEW CHARACTER 的標籤、性別、種族、陣營、職業（re_100、re_102）。
  - 物品名稱（NAME-1）與材質字首（re_100、re_101）。
  - EXE 內的訊息框、存讀檔提示、戰鬥彈出框、法術／靈能名稱、頭像狀態、USE 按鈕（re_103）。
  - 學法術卷軸下方的兩行文字（v118～v120，re_104 §16）。
- **操作改良（v107～v117，re_104）**：
  - 遊標模式熱鍵：空白鍵＝行走、`A`＝攻擊、`S`＝觀察、`T`＝動畫開關（原本在 `A`）。
  - 智慧遊標（非戰鬥時）：
    - 行走遊標點物件（NPC、門、箱子，不含隊員）：相鄰就互動；不相鄰就走過去，走到之後自動互動。
    - 按住 Ctrl 點：只移動，不互動。
    - 觀察遊標點太遠或視線被擋的東西：走過去，走到之後自動互動（戰鬥中維持原版訊息）。
    - 靜態物件（石棺、草堆）會走到旁邊的空格。
    - 懸停在可互動的物件上時，行走遊標會換成觀察圖示。
    - 攻擊遊標點搆不到的目標（沒有遠程手段）：走過去再攻擊。遠程攻擊照原版。
    - 從觀察／攻擊遊標開始「走過去」時，會先切回行走模式（非行走模式下世界是暫停的）。
  - 建置選項：`--cursor-hotkeys`、`--smart-cursor`（都需要 `--view-ui`）。
  - 玩家用的說明：`docs/新操作說明.md`。建置時如果有上述任一選項，
    會轉成純文字檔 `新操作說明.txt`（UTF-8 含 BOM），放在組合包根目錄。
- 各版本的細節：v90～v106 見 re_103（含附錄的逐版紀錄），v107～v120 見 re_104。

---

## 1. 下一步（依優先順序）

### 1.1 調整除錯功能的按鍵衝突（使用者指定為下一個 Session 的第一個目標，re_104 §17）

- 原版有開發者除錯模式，以命令列 `-k911` 開啟（`[11B0]=1`）。
- 操作改良佔用了除錯模式的幾個入口：
  - `S`、`T`：熱鍵分派表被 `--cursor-hotkeys` 改掉，`T` 的處理程式變成 FF87 stub 的所在地。
  - 上游按鍵表的 F6：改成直接結束，它的死碼放了懸停圖示的轉接碼（`0x1B81E`）。
  - 觀察、攻擊路徑的除錯亂數分支：被 `--smart-cursor` 的跳躍和 FF88 stub（`0x1B483`、`0x1B4EF`）取代。
- **使用者已同意的方案（2026-09-25）：改用組合鍵，不必另外找空間搬 stub。**
  - 原理：組合鍵的鍵值不同（Ctrl+S＝`1F13`、Ctrl+T＝`1414`、Alt+F6＝`6D00`），而分派表是比對完整的鍵值。
  - 表格長度固定，所以不新增項目，而是改掉**大寫那一筆**的鍵值。

  | 除錯功能 | 新按鍵 | 做法 |
  |---|---|---|
  | `S`（`[2C0:0357] += 1000`） | **Ctrl+S** | overlay 分派表（`0x71C1B` 值／`0x71C5D` 目標）裡大寫 `S`（索引 15）的鍵值 `1F53`→`1F13`，目標改回原本的處理程式 IP `13AC`。這段程式完整保留，本身會檢查 `[11B0]`。 |
  | `T`（寫 `0x989680` 並呼叫 `0628:0057`；小寫 `t` 則是 `0628:006B`） | **Ctrl+T**；Ctrl+Shift+T 對應原版大寫 `T` | 大寫 `T`（索引 11）的鍵值 `1454`→`1414`，導到 FF87 核心。原處理程式 `0x71198` 中間被 FF87 stub 蓋掉，所以由核心重寫：檢查 `[11B0]`，用 BIOS `0040:0017` 的 Shift 位元區分大小寫。呼叫 overlay 之後，一樣自己執行分派函式的結尾，不要返回 overlay 25（re_104 §7）。 |
  | 上游表 F6（`191F:00F1`、`28D1:0D7E`、`142F:0426`） | **Alt+F6** | 上游表（`1587:0FEB`，目標在 +34h）F6（索引 12）的鍵值 `4000`→`6D00`。原本的旗標檢查 `0x1B81E～0x1B827` 被懸停轉接碼佔用，主體 `0x1B828` 起還在，要另外補上 `[11B0]` 檢查（例如沿用 FF88 stub，用新的 CX 標記）。 |
  | `M`、`?`、`=` | 不變 | 沒有被佔用。 |
  | 觀察／攻擊的除錯亂數分支 | 放棄 | 不是按鍵觸發，已被智慧遊標取代。 |

  - 為什麼 F6 用 Alt：原版的除錯鍵本來就有 Alt+F1／F2／F4（上游表 `6800`／`6900`／`6B00`，都會檢查 `[11B0]`）。
    Ctrl+F6 在 DOSBox 系列可能是模擬器的快速鍵。
  - 為什麼 S、T 不用 Alt：DOSBox-X 視窗有選單列，Alt+字母可能會開選單。
  - 要避開 Alt+F4（Windows 關閉視窗）。
- 副作用：開著 CapsLock 時，`S`、`T` 熱鍵不會觸發（只剩小寫那一筆）。要寫進 `docs/新操作說明.md`。
- 三組按鍵都要在 DOSBox-X 實測，確認有送進遊戲。測除錯模式時，用 `-k911` 啟動。
- 做完之後，把方案和結果補進 re_104 §17（目前 §17 還沒有記錄組合鍵方案）。

### 1.2 視窗資源（WIND，在 RESOURCE.GFF）裡的按鈕

- 學法術卷軸的 EXIT、背包的 DROP／SPLIT 等。它們不在 EXE，要先找出 WIND chunk 的文字格式。
- v98 已經把 EXE 唯一的 EXIT 改成「離開」，但卷軸上仍是英文，所以卷軸的 EXIT 應該在 WIND 裡。

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
  --cursor-hotkeys --smart-cursor \
  --output scratch_test/cjk_display_staging_vNN_xxx
```

- **存檔**：建好後，從**使用者最後玩的那一版**複製**全部**存檔：`SAVE*.SAV`（使用者會存到第 10 格以上）、
  `DARKRUN.GFF`、`CHARSAVE.GFF`。
  - v107～v116 只複製了 `SAVE0?.SAV` 和 `DARKRUN.GFF`，漏掉 v109 的 `SAVE10.SAV` 和 `CHARSAVE.GFF`，後來才補進 v117。
  - 存檔名稱另存在別的檔，所以讀檔清單上的名字會跟遊戲內不同，但 SAVE01 本身是同一份。
- **GSTR 修補**：全域字串 GSTR 會存進存檔，讀舊存檔時英文標題會被還原。
  - 字串表每格 42 bytes，依序是 GSTR[1] What do you say?、[2] END、[3] CLOSE、[4] What do you do?……
  - 複製存檔之後，執行 `python tools/patch_save_gstr.py <組合包>/GAME/DARKSUN <對話封包 json>`：
    - 它會把 MAS-99 設定的 GSTR[1][4][5][6][7] 裡還是英文的改成中文。
    - 原檔備份為 `*.orig`。新開的遊戲不受影響。
- 只要對話封包改版，舊存檔記住的觸發器位址就可能失效（re_99）。
- **測試**：`python -m pytest tests -q`，目前 247 項全過。

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
- **快捷鍵**：主選單按 `L` → `Enter` 讀檔。`i` 開背包，`v` 開 VIEW CHARACTER，`1～4` 切換角色。
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
| 選單換頁／疊影 | `docs/re/re_96`～`re_98` |
| `%s` 迴圈解碼失敗紀錄 | `docs/re/re_52`、`re_53`、`re_63` |
| 玩家用操作說明 | `docs/新操作說明.md` |
| 名詞對照 | `docs/名詞權威對照表.md` |
