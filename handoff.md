# 《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands) 繁中化交接指南 (handoff.md)

> **產生時間**：2026-09-21 23:01（第 0、四節更新於 2026-09-24）  
> **交接目的**：為下一輪重開 Session 的 AI 助手提供完整無縫的專案背景、歷史數據、技術規範、標準操作 SOP 與接續目標，確保繁中在地化推進不中斷。

---

## ⚠️ 0. 最新狀態（2026-09-24 更新，新 Session 請先讀這一節）

### 0.1 現況

- **可玩版本**：`scratch_test/cjk_display_staging_v89_view_rows`（使用者已實機確認）。
- **已中文化**：
  - 全部對話（re_99）
  - 背包／VIEW CHARACTER 的標籤、性別、種族、陣營、職業（含多職業）
  - 物品名稱（NAME-1）
  - 物品材質字首（re_100、re_101）
- **v89 的修正**：第三職業顏色、VIEW CHARACTER 下半部四行行距（re_102）。
- **最新 commit**：`18c85ac`。

**下一輪目標（使用者指定）：翻譯寫在程式裡的字串**，例如選單下方的「WHAT DO YOU SAY?」。
使用者也注意到其他畫面還有英文字串。細節見 0.3 節。

### 0.2 重建 v89（`scratch_test/` 在 `.gitignore` 裡）

```bash
# 0) 候選清單：所有出現位置都是 GPL/MAS、inline、compressed、非 unresolved 的已翻譯單元
python - <<'EOF'
import json
from collections import defaultdict
occs = json.load(open('localization/catalog/dialogue_occurrences.json', encoding='utf-8'))['occurrences']
units = json.load(open('localization/catalog/dialogue_units.json', encoding='utf-8'))['units']
translated = {u['unit_id'] for u in units if u.get('translation_zh_tw', '').strip()}
by_unit = defaultdict(list)
for o in occs:
    if o.get('unit_id'):
        by_unit[o['unit_id']].append(o)
ok = sorted(uid for uid in translated if by_unit.get(uid) and all(
    not o.get('unresolved') and str(o.get('kind', '')).strip().upper() in ('GPL', 'MAS')
    and o.get('source') == 'inline' and o.get('sub_type') == 'compressed'
    for o in by_unit[uid]))
open('scratch_test/all_translated_unit_ids.txt', 'w', encoding='utf-8').write('\n'.join(ok))
print(len(ok))   # 13194
EOF

# 1) mapping（已 commit；只有新增字元時才重跑，兩個 catalog 都要給）
python tools/cjk_localization_pipeline.py inventory \
  --catalog localization/catalog/localization_manifest.csv \
  --catalog localization/catalog/fixed_ui_labels.csv

# 2) 字型 bank（mapping 有新字時才重建）
python tools/cjk_localization_pipeline.py build-banks --mapping localization/cjk_mapping.json \
  --output scratch_test/formal_cjk_fusion_10x10_v21_fixed_ui --font Fonts/Fusion_Pixel_10px.ttf \
  --font-size 10 --pixel-width 10 --height 10 --advance 10 --threshold 64 --fit-mode pixel-aligned

# 3) 對話封包 → 疊上 NAME-1
python tools/compile_gpl_dialogue_patch.py \
  --unit-id-file scratch_test/all_translated_unit_ids.txt --output scratch_test/gpl_full_from_pristine_v5
python tools/compile_gff_name_records.py \
  --prior-package scratch_test/gpl_full_from_pristine_v5/gpl-dialogue-patch.json \
  --output scratch_test/gpl_full_v5_name_records

# 4) 組合包
python tools/build_cjk_display_staging.py \
  --mapping localization/cjk_mapping.json \
  --bank-package scratch_test/formal_cjk_fusion_10x10_v21_fixed_ui/cjk-bank-set.json \
  --spin-package scratch_test/spin_gff_import_title_newline_v3_current/gff-text-replacements.json \
  --gpl-package scratch_test/gpl_full_v5_name_records/gpl-dialogue-patch.json \
  --ebox-line-gap 2 --menu-line-gap 2 --dialogue-option-pitch 11 --view-ui \
  --output scratch_test/cjk_display_staging_vNN_xxx
```

- 建好後，把 v86r6 的 `SAVE01～08.SAV` 與 `DARKRUN.GFF` 複製進去，讓使用者可以讀進度。
  存檔名稱另存在別的檔，所以讀檔清單上的名字會跟遊戲內不同，但 SAVE01 本身是同一份。
- 只要對話封包改版，舊存檔記住的觸發器位址就可能失效（re_99）。
- `tests/`：209 項全過，指令是 `python -m pytest tests -q`。

### 0.3 下一輪：程式內字串翻譯——已知事實與限制

**A. 字串從哪裡來**

1. **「WHAT DO YOU SAY?」這類選單標題其實不在 EXE 裡**：
   - 它們是 GPLDATA 的 `GSTR[1]`（553 個選單）、`GSTR[4]`（12 個），另有 19 個內嵌標題。
   - 目前刻意保留英文，記在對話封包的 `withheld`（re_99 §4）。
   - 原因是下方選單標題的繪製程式沒有中文路徑，而且目前還不知道是哪一段程式。
   - 要翻譯，得先找到這段繪製程式並補上 Base94 解碼，然後取消 withheld。可以從 WIND-3008
     對話選單與 re_96～re_98 的選單繪製研究往下追。
2. **EXE 的畫面字串都在 DGROUP 裡**：
   - DGROUP 在檔案 `0x48960`，執行期段為 `4B7A`。
   - 用「以 NUL 結尾、主要是英文字母」的條件篩選，約有 570 條，內容包括：
     - 遊戲選單（`GAME MENU`、`RETURN TO GAME`、`MUSIC ON`）
     - 戰鬥（`END TURN`、`GUARD`）
     - 背包錯誤訊息（`Too heavy a load to carry`）
     - 狀態（`Stunned`、`Dead`）
     - 法術效果（`Hasted`）
     - 商店（`NO DEAL!`、`SOLD!`）
     - 升級（`CHOOSE A SPELL,`）
     - 法術／靈能名稱（約 150 條）
   - 不含 GUI 錯誤訊息，這部分約 700 bytes，在 `38D7～3B97`。
   - 篩選程式：用 regex `(?<=\x00)[\x20-\x7e]{4,}(?=\x00)` 掃描 DGROUP，再排除檔名、錯誤訊息等。
   - `localization_manifest.json` 裡有 656 筆 `exe_*` 單元，都還沒翻，但混了大量雜訊，
     例如 `X?VCT?VC...`、`Borland C++`。要先清理再開始翻譯。

**B. 技術限制（開工前先想清楚）**

1. **位址換算**：檔案位移 = `0x5400` + (執行期段 − `0x824`) × 16 + 偏移。
   - 例：`339E:016D` → `0x30D0D`；`4B7A:0000` → `0x48960`。
   - 舊文件（re_94）用的 `0xD640` 是錯的。
2. **空間**：一個中文字編碼成 `^xy`，佔 3 bytes。字串在 DGROUP 裡長度固定，原地通常放不下，
   例如 `GAME MENU` 是 9 bytes，「遊戲選單」要 12 bytes。
   - 程式碼用立即值 `push 2403h` 之類引用字串，所以可以把字串搬到別處，再改這些立即值。
   - 問題是 DGROUP 沒有現成的空地：re_56 已證明 DGROUP 尾端不能用。
   - 可能的來源：`38D7～3B97` 這段 GUI 錯誤訊息，以及 `1FA5～1FDD` 的除錯字串。
     但必須先證明這些字串沒有其他引用、改掉不影響功能，才能拿來用。
3. **大多數 UI 繪製路徑不會解碼 Base94**：
   - 主線的常駐 resolver 只掛在 EBOX（對話框），還有 MENU 的行距修補。
   - 最通用的 formatter 是 `339E:016D`（`%C%s%d…`）：
     - `%s` 迴圈在 `339E:02E8`，檔案 `0x30BA0+0x2EB`，逐字呼叫 `11A4:59C1` 畫字。
     - v34／v35 曾經在這個迴圈加解碼，結果畫面空白或當機（re_52、re_53）。
       `build_cjk_display_staging.py` 目前會拒絕這兩個實驗旗標。
     - 這條路徑的前進量是固定的 `寬度('H')+1`，大約 7px（re_63）。10px 寬的中文字會重疊 3px。
   - 物品懸停列、右鍵資訊卡已經實測，都不會解碼（re_101 §2）。
   - 所以翻譯每一條字串之前，都要先確認它走哪條繪製路徑；也可以考慮設計一個安全的通用解碼點。
     這是下一輪的核心問題。
4. **可用的字元碼已經用完**：
   - name-slot 暫借了 10 個碼：`` " # & < > \ ~ ` _ | ``。
   - 材質字首用了 6 個碼：`* @ [ ] { }`。
   - 這 16 個字元只要出現在任何畫面文字裡，就會被畫成中文字形。re_101 §7 的「貝」就是這樣來的：
     `<` 被畫成了殘留的中文字。
   - 所以翻譯後的字串不能含這些字元。看到英文裡夾著莫名的中文字，先查它原本是不是其中之一。
5. **修補 overlay 區**：必須用 `plan_name_slot_consumers.verify_overlay_relocations` 檢查，
   並確認沒碰到 MZ 重定位。`view_ui_layer.apply_view_ui_exe_patches` 是現成的範例。
6. **會被引擎比對的字串不能翻**：
   - `END`、`CLOSE`、`DEBUG`、玩家打字比對的關鍵字、`string compare` 的對象（re_99）。
   - DGROUP 的 `CLOSE`（`1F11`）、`DEBUG`（`1F17`）就是其中之一。

**C. 建議的起手式**

1. 請使用者提供想先處理的畫面截圖或字串（使用者說「有發現一些地方還有其他字串」）。
2. 對每一條字串：
   - 找出引用它的程式碼（搜尋 `push <DGROUP偏移>` 等立即值）。
   - 判斷它走哪條繪製路徑。
   - 評估「原地放得下嗎？」、「路徑會解碼嗎？」。
3. 如果大量字串都走 `339E:016D`，就研究在 formatter 加一個**窄範圍**的 Base94 解碼：
   - 先讀 re_52、re_53、re_63，了解當年失敗的原因。
   - 同時處理 7px 固定前進量的問題。
4. 譯名以 `docs/名詞權威對照表.md` 為準。法術、靈能名稱在對照表裡大多已經有智冠手冊的定名。

### 0.4 其他待辦

1. **避頭點**：換行偶爾會讓「，」「。」出現在行首。
2. **已知風險（目前沒有症狀）**：常駐字型快取 `2E86:545A～5533` 和 name-slot trampoline
   `2E86:5414`，都在計時器 ISR 的私有堆疊 `53B6～55A6` 裡。若出現隨機花字或當機，從這裡查。
3. **名詞**：Psionicist 維持「靈能師」（使用者 2026-09-24 決定），Thief 用「小偷」。

### 0.5 操作注意（本輪學到的）

- **DOSBox-X-AI**：
  - 一律用 PowerShell `Start-Process` 啟動（`-WorkingDirectory` 指到組合包根目錄）。
  - 重開之前，要等 9876 埠釋放。否則新執行個體的 bridge 綁定失敗，會整個停用，
    這時只能再重開一次。
  - 關掉使用者可能正在玩的執行個體之前，要先問。
- **滑鼠座標**：`move_mouse_absolute` 的 x 要用擷取畫面上的 x 乘 2（擷取寬 640，遊戲內容在左半），
  y 不變。
- **快捷鍵**：主選單按 `L` → `Enter` 讀檔。`i` 開背包，`v` 開 VIEW CHARACTER，`1～4` 切換角色。
- **記憶體**：讀之前先 `pause_execution`；讀完記得 `continue_execution`。
- **組合包目錄被佔用**：DOSBox 開著組合包時，那個目錄刪不掉。重建時請換一個新的輸出目錄名。
- **Python 腳本**：寫在 Bash heredoc 裡時，`\x..` 會被轉成真的控制字元。請把腳本寫進暫存目錄的檔案再執行。
- **Unicorn 模擬測試**：同一位址改寫程式碼之後，Unicorn 會沿用舊的翻譯快取。每個 stub 要放在不同位址。

### 0.6 相關文件

| 主題 | 文件 |
|---|---|
| 對話全量編譯、GPL 池、withheld | `docs/re/re_99_*` |
| 背包／VIEW CHARACTER 併入主線 | `docs/re/re_100_v87_view_ui_merge.md` |
| 材質字首、固定字元碼、天生攻擊括號 | `docs/re/re_101_v88_material_words.md` |
| 職業顏色、行距、位址換算更正 | `docs/re/re_102_v89_class_colour_and_view_rows.md` |
| 選單換頁／疊影 | `docs/re/re_96`～`re_98` |
| `%s` 迴圈解碼失敗紀錄 | `docs/re/re_52`、`re_53`、`re_63` |

---


## 一、重大歷史成就與當前進度總覽

> ⚠️ 以下統計是 **2026-09-21 的歷史快照**，已過時。2026-09-23 實際狀態：
> `dialogue_units.json` 對話單元 **13,295 / 13,295（100%）** 已翻譯；
> `localization_manifest.json` 全遊戲總清單 **13,845 / 14,529** 已翻譯（未譯 684 筆，多為非對話類）。
> 瓶頸已不在翻譯，而在「把翻譯編進 EXE」（見第 0.4 節）。

本專案致力於將經典 CRPG **《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands)** 進行全文本高品質繁體中文在地化（嚴格依循臺灣智冠官方譯本手冊「珍288」與 AD&D 2nd Edition 經典規則）。

在本輪對話中，連續大批次完封了 **GPL-141 至 GPL-150** 等全部 10 個腳本區塊（本輪累計新譯 **735 筆**對話單元），連續突破各項歷史紀錄：

1. **全遊戲文本總量正式逼近 66%**：
   * **全清單總單元 (`TOTAL ALL`)**：**`9,577 / 14,529`（`65.92%`）**，已達 9,577 筆！
2. **對話單元正式突破 9,000 筆大關（67.9%）**：
   * **對話單元 (`dialogue`)**：**`9,027 / 13,295`（`67.90%`）**，已達 9,027 筆，全遊戲未譯對話已降至 4,268 筆！
3. **腳本連續無斷點大貫通（150 個腳本 100% 零死角）**：
   * **`GPL-1` 至 `GPL-150` 全部 150 個腳本 100% 完封，無任何一筆遺漏**（含 GPL-81、GPL-84 全面清盤補全，GPL-98、GPL-113 無對話純邏輯腳本，MAS-99 全域 UI 提詞，共 148 個實體劇情對話腳本全勝）！
4. **全書英文單詞翻譯量達 68.1%**：
   * **英文單詞 (`Words`)**：**`82,037 / 120,514`（`68.07%`）**，正式突破 82,000 詞大關！
5. **遊戲實機出現次數突破 72.4% 大關**：
   * **實機呼叫 (`Occurrences`)**：**`13,778 / 19,026`（`72.42%`）**，正式達到 13,778 次！
6. **動態 CJK 繁中字庫管線**：
   * 收錄字符 **`2,779 字`**（分佈於 11 個 Bank），容量餘裕達 8,835，`inventory` 與 `compile-catalog` 100% 驗證通過，0 錯誤。
7. **權威名詞對照表**：
   * [`docs/名詞權威對照表.md`](file:///d:/git/Dark%20Sun%20Series/docs/%E5%90%8D%E8%A9%9E%E6%AC%8A%E5%A8%81%E5%B0%8D%E7%85%A7%E8%A1%A8.md) 定版至 **v4.7**，收錄 **757 條**審定專有名詞（增補提奧菲爾、卡夏）。

---

## 二、重要系統環境與注意事項（⚠️ 必讀）

1. **背景常駐任務警告**：
   * 終端機中有一項長期執行的橋接注入程序：`python scratch_test/run_bridge_injection.py`。
   * **⚠️ 絕對不要終止、中斷或 kill 此程序**，請保持其在背景靜默運行。
2. **作業系統與環境**：
   * 作業系統：Windows (PowerShell)。
   * Python 環境：根目錄下直接可用 `python`。
   * 檔案編碼：所有 JSON / Python 檔案使用 `utf-8`，CSV 檔案使用 `utf-8-sig`。
3. **使用者推進風格**：
   * 使用者明確指示：**「可以一次多翻一點 / 一次堆翻一點」**。
   * 請維持大批次（通常為 100～150 筆左右，或 2~4 個中小型 GPL 腳本）連續推進，不要拆碎成過小的單一腳本請求確認。

---

## 三、四大核心檔案同步與空白規範

每次翻譯新腳本時，必須**同時、嚴格同步更新**以下 4 個主目錄檔案：

| 檔案路徑 | 格式 | 說明 |
| :--- | :--- | :--- |
| `localization/catalog/dialogue_units.json` | JSON (utf-8) | 對話單元主庫（含 summary 計數更新） |
| `localization/catalog/dialogue_units.csv` | CSV (utf-8-sig) | 對話單元表格庫 |
| `localization/catalog/localization_manifest.json` | JSON (utf-8) | 全遊戲在地化總清單（含 summary 計數更新） |
| `localization/catalog/localization_manifest.csv` | CSV (utf-8-sig) | 全遊戲在地化總清單表格 |

### ⚠️ 空白對齊鐵律 (Whitespace Alignment Rule)
在《浩劫殘陽》遊戲引擎中，字串開頭與結尾的空格有嚴格的語法或 UI 選項排版意義：
- 選項開頭通常有 2 個空格（`L2:T0`），如 `"  Yes, I agree."` -> `"  是的，我同意。"`。
- 句子拼接前半段通常有結尾空格（`L0:T1`），如 `"I saw him "` -> `"我看見了他 "`。
- 句子拼接後半段通常有開頭空格（`L1:T0`），如 `" in the city."` -> `" 在城鎮裡。"`。
- **所有翻譯字串必須在寫入前經由腳本驗證 `leading_spaces` 與 `trailing_spaces`，必須與原始英文字串完全一致！**

---

## 四、接續推進目標（下一輪重開直接執行）

~~從原版一次重編全部對話翻譯進 EXE~~：已完成（v86r6，re_99）。
~~合併屬性（VIEW CHARACTER）與物品中文化~~：已完成（v87～v89，re_100～re_102）。

**下一個目標：翻譯寫在程式裡的字串（選單標題、EXE 畫面字串）**，已知事實、限制與起手式見第 0.3 節。
