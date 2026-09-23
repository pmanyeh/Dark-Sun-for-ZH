# 《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands) 繁中化交接指南 (handoff.md)

> **產生時間**：2026-09-21 23:01（第 0、四節更新於 2026-09-23 晚間）  
> **交接目的**：為下一輪重開 Session 的 AI 助手提供完整無縫的專案背景、歷史數據、技術規範、標準操作 SOP 與接續目標，確保繁中在地化推進不中斷。

---

## ⚠️ 0. 最新狀態（2026-09-23 晚間更新，新 Session 請先讀這一節）

### 0.1 一句話現況

**對話翻譯已全部編進遊戲**。目前可玩的是 `scratch_test/cjk_display_staging_v86r6_gpl_pool`
（使用者已實機確認）：215 個對話區塊全數編入，中文換行、「我是<名字>」選項、句中多餘
空格、Trustee 等大腳本的 BAD GPL EXIT 都已修好。細節見 `docs/re/re_99_*`。

**下一步（使用者指定）**：把 VIEW CHARACTER 屬性畫面與物品／背包的中文化合併進這條
主線，見第 0.4 節。

### 0.2 這次 Session 做了什麼（細節見 re_99）

| # | 問題 | 修法 | 位置 |
|---|---|---|---|
| 1 | EXE 只含 106 個區塊的中文 | 從原版一次全量編譯；GPL-3 `0x07C0` 固定入口是誤判（真正的呼叫者是 MAS-42 的 boxtrigger），已不需要 `--require-fixed-entry` | `compile_gpl_dialogue_patch.py` |
| 2 | 26 個區塊被整段跳過 | 支援 `string copy`（0x0A，「Goodbye.」就在 MAS-99）、選單內嵌標題、`GFFI-7` | 同上 |
| 3 | 對話框關不掉、選單標題亂碼 | `END`/`CLOSE`/`DEBUG` 是引擎控制字；選單標題沒有中文繪製路徑，這 23 筆記入封包的 `withheld`，保留英文 | 同上 |
| 4 | 每段譯文都另起一行 | EBOX 只在空白處斷行；每個中文字之後都視為可斷點（`147D:00FC` far routine） | `patch_dsun_scratch_cache.py` |
| 5 | `I'm 0001` | strcpy 來源改指 `147D:015C`「我是」 | 同上、`build_cjk_display_staging.py` |
| 6 | 「我已經在 這裡」 | 編譯時去掉中文接縫處的空格（目錄不動） | `compile_gpl_dialogue_patch.py` |
| 7 | Trustee 對話出現 BAD GPL EXIT | GPL 記憶體池只有 10,000 bytes，GPL-146 翻譯後 10,706；`0x6A694` 改為 12,288，編譯器會擋下超過上限的 chunk | `patch_dsun_scratch_cache.py` |

### 0.3 重建 v86r6 的完整指令（`scratch_test/` 在 `.gitignore` 裡）

```bash
# 1) 候選清單：所有出現位置都是 GPL/MAS、inline、compressed、非 unresolved 的已翻譯單元
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

# 2) 對話封包（從原版全編；不要加 --prior-package 或 --require-fixed-entry）
python tools/compile_gpl_dialogue_patch.py \
  --unit-id-file scratch_test/all_translated_unit_ids.txt \
  --output scratch_test/gpl_full_from_pristine_v4

# 3) 組合包
python tools/build_cjk_display_staging.py \
  --mapping localization/cjk_mapping.json \
  --bank-package scratch_test/formal_cjk_fusion_10x10_v20_current/cjk-bank-set.json \
  --spin-package scratch_test/spin_gff_import_title_newline_v3_current/gff-text-replacements.json \
  --gpl-package scratch_test/gpl_full_from_pristine_v4/gpl-dialogue-patch.json \
  --ebox-line-gap 2 --menu-line-gap 2 --dialogue-option-pitch 11 \
  --output scratch_test/cjk_display_staging_v86r6_gpl_pool
```

v86r6 雜湊：`DSUN.EXE` `74634c98…`、`GPLDATA.GFF` `2346f98a…`、`RESOURCE.GFF` `7083e879…`。
封包數據：248 個 chunk、13,692 個編入、23 個 withheld。

**編譯後務必驗證跨區塊參照**（re_99 §1 的做法）：用 `gpl-disasm --all --json` 反組譯
原版與新版，逐條比對 `CROSS_CHUNK_TARGET` 指令與 GPLI-1，目標要等於
`instruction_offset_map` 的結果，其他參數要完全相同。

### 0.4 下一步：合併屬性（VIEW CHARACTER）與物品中文化

這條線的成果在另一條舊的 build 鏈上，**從未併入 `build_cjk_display_staging.py`**：

- 最終 checkpoint：`scratch_test/cjk_display_staging_v75_view_column_shift2`
  （交接文件 `docs/re/HANDOFF_NEXT_SESSION_2026-09-18.md`，完整記錄 `re_85`～`re_95`）。
- build 鏈：v33（`build_name_slot_candidate_from_v33.py`）→ 背包、能力值、固定標籤、
  materials → `build_view_*_candidate.py` 一路疊到 v71（`build_view_class_multi_candidate.py`）
  → v72～v75（`build_view_layout_adjust*`、`build_view_column_shift*`）。每一版都以上一版的
  staging 目錄當 parent，依賴舊的字型與 mapping。
- 核心：`tools/plan_name_slot_consumers.py`、`tools/cjk_name_slot_cache.asm`。

**已知障礙（開工前先看）**：

1. **bank 數量**：name-slot 規劃寫死「6 個 CJB1 bank」（`plan_name_slot_consumers.py` 第
   227／233／250 行）。現行主線是 12 個 bank，`tests/` 裡的 19 個 errors 就是這個原因
   （`...eight IDs within six banks`）。
2. **mapping 不同**：v75 用的是 `cjk-mapping-v57.json`（1,330 字）；主線是
   `localization/cjk_mapping.json`（12 bank）。所有字 ID 都要重新對應。
3. **記憶體位置衝突要逐一核對**：
   - `147D` 死區已經用滿（re_99 §9），name-slot 不能再往這裡放。
   - name-slot 使用 FONT payload（`FONT_CORE_PAYLOAD_OFFSET = 0x239B`）與常駐段
     `0x51F1`／`0x5414`。`2E86:51F0~55AA` 是計時器 ISR 的私有堆疊（re_98 §29.1），
     常駐字型快取 `545A~5533` 本來就只剩約 115 bytes 餘裕，合併後要重新評估。
   - 修補 overlay 區時，要用 `verify_overlay_relocations` 檢查（re_95：`0x8A1E4` 曾撞上
     overlay relocation）。
4. 建議做法：先讀 09-18 交接與 `re_94`／`re_95`，把 name-slot 系列的 EXE／RESOURCE 修補
   整理成可以接在 `build_cjk_display_staging.py` 後面的步驟，以 v86r6 為基底；不要以 v75
   為基底把對話修補倒灌回去。

### 0.5 其他待辦

1. **選單標題仍是英文**（What do you say? 等）：要先找出下方選單標題的繪製程式並加入
   中文路徑，才能取消 `withheld` 中的標題項目。
2. **避頭點**：換行偶爾會讓「，」「。」出現在行首。
3. **已知風險（目前無症狀）**：常駐字型快取 `2E86:545A~5533` 與計時器 ISR 私有堆疊重疊，
   餘裕約 115 bytes。若出現隨機花字或當機，從這裡查。

### 0.6 本次學到、下次要記得的事

- **存檔會記住已登記的觸發器位址**。每次對話封包改版，腳本位址都可能移動，舊存檔在同區域
  可能出現奇怪行為。判斷是不是真 bug 時，先用新遊戲重現。
- **大小也是限制**：GPL chunk 上限是池大小減 2（現為 12,286）。編譯器會擋下，但若再調大池，
  要一併確認記憶體是否足夠。
- **引擎會讀的字串不能翻**：`END`／`CLOSE`／`DEBUG`、玩家打字比對的關鍵字、`string compare`
  的對象。新增可翻譯的指令類型前，先查這些。
- **DOSBox-X-AI bridge 回應 id 錯位**只能結束 `dosbox-x.exe` 再重開。讀記憶體前要先
  `pause_execution`。段位址換算：檔案段 + `0x824` = 執行期段（例：`3781` → `3FA5`）。
- 在 Bash heredoc 裡用 Python 寫入原始碼時，`\x..`／`\0` 會變成實際的控制字元；改用暫存目錄
  的腳本檔。

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

~~從原版一次重編全部對話翻譯進 EXE~~：已完成（v86r6，見第 0 節與 re_99）。

**下一個目標：合併屬性（VIEW CHARACTER）與物品中文化**，細節與已知障礙見第 0.4 節。
