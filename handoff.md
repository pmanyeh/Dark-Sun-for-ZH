# 《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands) 繁中化交接指南 (handoff.md)

> **產生時間**：2026-09-21 23:01  
> **交接目的**：為下一輪重開 Session 的 AI 助手提供完整無縫的專案背景、歷史數據、技術規範、標準操作 SOP 與接續目標，確保繁中在地化推進不中斷。

---

## ⚠️ 0. 最新狀態（2026-09-23 更新，新 Session 請先讀這一節）

### 0.1 一句話現況

v85 已重建完成，使用者**實機確認**：Kurzak 手動對話、進奴隸營房自動觸發、中文對話與選項、
四選一換頁無殘影，全部正常。改動已併回 `main` 並推上 GitHub（`origin/main`）。目前可玩的組合包是 `scratch_test/cjk_display_staging_v85r5_triggers`。

**歷史中的 `019658b`～`6cfb505`（舊 v85 的 4 個 commit）不可用**：它們把修補程式與字型檔名
放進會被遊戲覆寫的記憶體，中文會全變「?」。其後的 `90d1bb5`、`e585108` 已修正，以目前 `main` 為準。

### 0.2 這次 Session 修了什麼（細節見 re_98 第 29～33 節）

| # | 問題 | 根因 | 修法 | 位置 |
|---|---|---|---|---|
| 1 | 舊 v85 中文全變「?」、各種異常 | 修補程式、面板像素、bank 檔名放在 `2E86:D730`，其實是遠資料段 `3BF6` 的執行期緩衝區 | 換頁修補改放 `147D:0010`（段表證實無人引用的死區），建置時組譯；面板以 2-bit 壓縮 | `tools/dialogue_choice_top_rows_hook.asm`、`tools/patch_dialogue_menu_wind.py` |
| 2 | 12 個字型 bank 放不下 | 原 bank 檔名表只有 42 bytes 空間（最多 8 個 bank） | 超過 8 個 bank 時，以可重定位的 `push 0x147D; pop ds` 讀取 `147D:0110` 的檔名表；常駐快取仍卡在 `0x5534` | `tools/cjk_scratch_cache.asm`、`tools/patch_dsun_scratch_cache.py` |
| 3 | 對話仍是英文 | EXE 內的對話編譯包 `gpl_current_v85` 只編了 215 個 GPL 區塊中的 99 個；GPL-141 因選單含 `GSTR[5]` 變數選項被整段跳過 | 選單中的非字面選項（變數、`INTRODUCE`）原樣保留，不再整段跳過 | `tools/compile_gpl_dialogue_patch.py` |
| 4 | v85r3 點 NPC 不會對話 | 編譯器只修正同區塊內跳轉；別的區塊指進來的呼叫／觸發器留在舊位址 | 編完後全檔對照「舊位址→新位址」，修正所有 `0x14` 呼叫與觸發器；結果可重跑、不會重複修改 | 同上 |
| 5 | 進奴隸營房不自動觸發 | 視線觸發 0x1B/0x1C 沒列入；格子／區域觸發 0x68/0x6A 的位址參數位置寫錯（前面其實是座標） | 修正對照表；全檔 2,869 個呼叫／觸發器，除位址外參數與原版逐一比對一致，剩餘過期參照 0 | 同上 |

第 4、5 項同時修掉了舊包本來就有的錯誤：最終一共修正 859 個跨區塊參照。舊 v85 的
「很多問題」很可能也和它們有關。

### 0.3 重建 v85r5 的完整指令（`scratch_test/` 在 `.gitignore` 裡，檔案不在 git 中）

```bash
# 1) 對話編譯包：以舊包為底，加上 GPL-141/143（及連帶的 50/117/142）
#    scratch_test/gpl141_143_unit_ids.txt = GPL-141/143 中所有已翻譯、inline 壓縮、
#    且沒有出現在舊包已修補區塊的 unit_id（212 筆）
python tools/compile_gpl_dialogue_patch.py \
  --prior-package scratch_test/gpl_current_v85/gpl-dialogue-patch.json \
  --unit-id-file scratch_test/gpl141_143_unit_ids.txt \
  --require-fixed-entry "GPL:3:1984:42" \
  --output scratch_test/gpl_current_plus141_v4

# 2) 組合包（12 個 bank、現行對照表與譯文、四選一換頁）
python tools/build_cjk_display_staging.py \
  --mapping localization/cjk_mapping.json \
  --bank-package scratch_test/formal_cjk_fusion_10x10_v20_current/cjk-bank-set.json \
  --spin-package scratch_test/spin_gff_import_title_newline_v3_current/gff-text-replacements.json \
  --gpl-package scratch_test/gpl_current_plus141_v4/gpl-dialogue-patch.json \
  --ebox-line-gap 2 --menu-line-gap 2 --dialogue-option-pitch 11 \
  --output scratch_test/cjk_display_staging_v85r5_triggers
```

v85r5 雜湊：`DSUN.EXE` `986fed16…`、`GPLDATA.GFF` `2e50202e…`、bank 12 個。測試用存檔從
`scratch_test/cjk_display_staging_v84_menu_padding_test/GAME/DARKSUN/SAVE0*.SAV` 複製。

### 0.4 待辦（依優先順序）

1. **把剩下約 110 個 GPL 區塊的翻譯編進 EXE（最重要）**
   - 翻譯本身已完成（`dialogue_units.json` 13,295/13,295），但 EXE 只含 106 個區塊的中文。
     遊戲中大部分仍見到的英文都是這個原因。
   - 應改為**從原版 `GPLDATA.GFF` 一次重編所有翻譯**，不要再用 `--prior-package` 疊加：
     舊包會擋住多個區塊共用的句子（例如 GPL-143 的 4 句，含 `"Never mind."`）。
   - 已知阻礙：之前一次全編時，GPL-3 的固定入口 `0x07C0` 被推移，`--require-fixed-entry`
     擋下建置（re_43：那是從 GPLDATA 以外被呼叫的出口入口，必須保持在原位址且以 `0x2A` 開頭）。
     需要讓 GPL-3 在 `0x07C0` 之前的譯文總長度維持不變，或找出其他方法。
   - 單元篩選：只能選「每個出現位置都是 GPL/MAS、inline、compressed、非 unresolved」的
     unit（全部 13,295 中有 13,194 筆符合）。其他 101 筆需要另外的匯入方式。
   - 全編完成後務必實機測：自動觸發、對話、出口轉場、戰鬥觸發。
2. **「Goodbye.」選項未翻譯**：GPL-141 `0x0A98` 選單最後一個選項是 `GSTR[5]`，文字由別處寫入
   （目錄推測的 `Hamonde` 是錯的）。要先找出寫入來源；使用者推測可能跟 Yes/No 一樣寫死在
   EXE 中。
3. **已知風險（目前無症狀）**：常駐字型快取 `2E86:545A~5533` 與計時器 ISR 的私有堆疊
   （`33A5` 段，`cs:01B6~03B6`，`"Test"` 為溢位標記）重疊，餘裕約 115 bytes。若出現
   隨機花字或當機，從這裡查。

### 0.5 本次學到、下次要記得的事

- **「檔案裡是 0」不代表執行期沒人用**。要找空位，先查 Borland 段表（`0x41378` 起，每筆 8 bytes：
  段、大小、旗標…），再檢查所有遠指標與 `cs:` 相對參照。目前唯一證實的死區是
  `147D:000F~0163`，已用掉：`0010~00FB`（換頁修補）、`0110~` 起（bank 檔名表）。
- **地圖座標在前、位址在後**：`move boxtrigger x, y, w, h, offset, chunk, flag`。檢查新指令格式
  時，用 `gpl-disasm --all` 看全遊戲的實例，不要只憑名稱猜。
- **存檔會保存已登記的觸發器位址**。用舊版本、而且人已在相關區域時存的檔，測試新版本時
  觸發器仍會是舊位址；要用進入該區域之前的存檔測。
- `build_cjk_display_staging.py` 目前**沒有**串接 VIEW CHARACTER／背包等 name-slot UI 修補，
  那些畫面顯示英文是預期中的，不是回歸。`tests/` 中有 1 failed、19 errors
  （`test_fixed_labels_candidate` 等 name-slot 相關）在本次改動前就存在。
- 對照用反組譯：`scratch_test/GPL-141.asm`（原版）、`GPL-141.patched.asm`。產生方式：
  `vendor/opends/target/release/gpl-disasm.exe <GPLDATA.GFF> --kind GPL --id 141 -o <out>`。

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

~~GPL-151～154 翻譯批次~~：已完成，對話單元已 100% 翻譯，舊的翻譯 SOP 不再是下一步。

**下一個目標：從原版一次重編全部對話翻譯進 EXE**，細節見第 0.4 節第 1 項。建議步驟：

1. 產生候選清單：
   ```bash
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
   ok = sorted(
       uid for uid in translated
       if by_unit.get(uid) and all(
           not o.get('unresolved')
           and str(o.get('kind', '')).strip().upper() in ('GPL', 'MAS')
           and o.get('source') == 'inline' and o.get('sub_type') == 'compressed'
           for o in by_unit[uid])
   )
   open('scratch_test/all_translated_unit_ids.txt', 'w', encoding='utf-8').write('\n'.join(ok))
   print(len(ok))   # 預期 13194
   EOF
   ```
2. 從原版全編（**不要**加 `--prior-package`）：
   ```bash
   python tools/compile_gpl_dialogue_patch.py \
     --unit-id-file scratch_test/all_translated_unit_ids.txt \
     --require-fixed-entry "GPL:3:1984:42" \
     --output scratch_test/gpl_full_from_pristine_v1
   ```
   上次在這一步失敗：`GPL-3: fixed external entry 0x07C0 must start with 0x2A, found 0x00`。
   先處理 GPL-3（re_43 第 1 節：v21 只重組 entry 前兩句競技場旁白讓長度回到 2307 bytes）。
   其他以 `skip GPL-n: ...` 列出的區塊，逐一檢查原因。
3. 用第 0.3 節的 `build_cjk_display_staging.py` 指令換上新包建置，實機驗證。
4. 更新 `docs/re/re_98…` 或開新的 re 文件，並更新本檔第 0 節。
