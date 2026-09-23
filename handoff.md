# 《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands) 繁中化交接指南 (handoff.md)

> **產生時間**：2026-09-21 23:01  
> **交接目的**：為下一輪重開 Session 的 AI 助手提供完整無縫的專案背景、歷史數據、技術規範、標準操作 SOP 與接續目標，確保繁中在地化推進不中斷。

---

## ⚠️ 0. 最新狀態（2026-09-23，第二輪更新）：v85 EXE 已用最新翻譯重建，尚未
commit、對話換頁的中文顯示尚未經使用者實機確認

**背景**：`main` 分支上已 commit 的 v85（`019658b` 起四個 commit）把對話選項換頁
修補程式、面板像素、12 個字型 bank 檔名放進了 `2E86:D730` 這塊「檔案裡看起來是
0」的位置，但那其實是**執行中會被覆寫的遠資料段（`3BF6`）**。實機測試會導致
bank 檔名損毀（中文全變「?」）與各種異常，**這幾個已 commit 的版本不可用**。

**本輪已做的修正（分兩階段）**：

1. **第一階段**：對話選項修補改寫成 `tools/dialogue_choice_top_rows_hook.asm`，
   改放在 `147D:0010`（段表確認的真正死區，只有一個不相關函式引用 `cs:0164`，
   前面完全沒有指標或程式碰它），組譯後 236 bytes，建置時才組譯。第一階段為了
   單獨驗證這個修法，暫時把 bank 數量還原回 v84 的 9 個上限，導致當時重建的
   `scratch_test/cjk_display_staging_v85r_choice_top_rows/` 只有 v84 的舊翻譯
   （6 個 bank），使用者實機測試時看到對話仍是英文——**這不是漏翻，是這個
   中繼版本本來就沒接上最新翻譯**。
2. **第二階段**：找出「12 個字型 bank 的檔名表」也需要一塊獨立死區，但因為
   `cjk_cache_start` 開檔時用的是「相對於 `CS`（執行期段 `2E86`）」的近位移，
   檔名字串**不能**搬到跟選項修補同一個（數值更小、不可定址）的 `147D` 段。
   解法：把「開檔用的 DS」本身改成一個可重定位的立即值——`push 0x147D`／
   `pop ds`，比照選項修補的做法登記進 MZ 重定位表；檔名字串仍放在 `147D`，
   只是位移換成 `0x0110`（跟選項修補的 hook 錯開 20 bytes，互不重疊）。同時
   把整條開檔序列重新設計成剛好比原本少一個 byte，讓常駐快取（bank 數量
   無論 8 個還是 12 個）都精準卡在原本驗證過的 `0x5534` 天花板，不需要放寬
   這個邊界。技術細節見 re_98 第 30 節。
3. 已用**現行最新翻譯**（`localization/cjk_mapping.json` 12-bank 對照表、
   `formal_cjk_fusion_10x10_v20_current`、`spin_gff_import_title_newline_v3_current`、
   `gpl_current_v85`，4126 筆已修補對話）＋新選項修補，重建
   `scratch_test/cjk_display_staging_v85r2_choice_top_rows_full/`。
   `RESOURCE.GFF` 雜湊與舊（有問題的）v85 manifest 一致，證明翻譯內容確實
   對齊到最新進度。
4. 實機驗證過：開機、讀取 SAVE01、開合選單、開啟 VIEW CHARACTER 均正常無
   當機。**VIEW CHARACTER 顯示英文屬於已知、不相關的既有限制**：該畫面的
   中文標籤來自另一條完全獨立、`build_cjk_display_staging.py` 目前沒有串接
   的 name-slot patch 管線（`tools/plan_name_slot_consumers.py` 相關測試在
   本次改動之前的 `main` 上就已經是失敗狀態）。本輪嘗試用滑鼠／鍵盤操作重現
   「WHAT DO YOU SAY?」對話換頁畫面但沒有穩定成功（遠端輸入在這個 isometric
   點按式移動的遊戲裡不好精準對位），**對話中文顯示與換頁殘影是否真的修好，
   最終仍需要使用者自己在遊戲裡進對話、按 Down 換頁確認**。
5. 所有改動都還停留在工作目錄，**尚未 `git commit`**。若使用者確認
   `cjk_display_staging_v85r2_choice_top_rows_full` 效果正常（中文對話顯示、
   換頁不再殘影、不當機），下一步才是 commit。
6. 額外發現但**不影響本次修正**、留意即可：既有的 CJK 字型快取
   （`2E86:545A~5533`）位在計時器中斷處理程式的私有堆疊深處，只剩約 115
   bytes 餘裕；`v84_menu_padding_test` 資料夾裡的 `GPLDATA.GFF` 與它自己
   build-manifest 記錄的雜湊對不上（看起來是 build 之後又被改過，不是
   build 腳本的錯）。

7. **第三輪（對話仍是英文）**：原因是 EXE 內的對話編譯包 `gpl_current_v85` 只編了
   215 個 GPL 區塊中的 99 個，不是漏翻（`dialogue_units.json` 已 100% 翻譯）。
   已修正編譯器處理「選單含變數選項／INTRODUCE 選項」的限制，把 GPL-141/143
   補進去，組合包為 `scratch_test/cjk_display_staging_v85r3_gpl141`。
   其餘約 110 個區塊仍待一次從原版重編（見 re_98 第 31 節）。

8. **第四輪（v85r3 無法觸發對話）**：編譯器沒有修正「別的區塊指進來」的呼叫與
   觸發器（例如 MAS-41 的對話觸發器仍指向 GPL-141 舊位址）。已加入全檔跨區塊修正，
   一次修了 577 個參照（含舊包原本就錯的）。組合包 `scratch_test/cjk_display_staging_v85r4_cross_chunk`：手動對話、中文、
   換頁皆經使用者確認 OK。見 re_98 第 32 節。

9. **第五輪（進奴隸營房不會自動觸發 Kurzak）**：視線觸發（0x1B/0x1C）、走入
   格子／區域觸發（0x68/0x6A）的位址參數位置在編譯器裡寫錯或漏列，從來沒被修正。
   修正後又多修了 282 處。**請測 `scratch_test/cjk_display_staging_v85r5_triggers`**，
   並用進入奴隸營房之前的存檔。另「Goodbye.」選項（`GSTR[5]`）尚未翻譯，另案處理。
   見 re_98 第 33 節。

技術細節（根因反組譯過程、段表證據、新 hook 與 bank 檔名死區逐行反組譯）記錄在
[`docs/re/re_98_dialogue_choice_paging_ghosting_investigation.md`](docs/re/re_98_dialogue_choice_paging_ghosting_investigation.md)
第 29、30 節，不在此重複。

---

## 一、重大歷史成就與當前進度總覽

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

下一個推進目標為 **GPL-151、GPL-152、GPL-153、GPL-154** 組合大批次：

### 目標腳本資訊：
- **`GPL-151`**：未譯單元 40 筆。
- **`GPL-152`**：未譯單元 27 筆。
- **`GPL-153`**：未譯單元 42 筆。
- **`GPL-154`**：未譯單元 8 筆。
- **合計規模**：約 117 筆未譯單元，是極度完美的單一批次（100–120 筆）！

### 接續標準 SOP：
1. **提取未譯單元**：
   ```bash
   python -c "
   import json
   with open('localization/catalog/dialogue_occurrences.json', 'r', encoding='utf-8') as f:
       occs = json.load(f)['occurrences']
   with open('localization/catalog/dialogue_units.json', 'r', encoding='utf-8') as f:
       units = {u['unit_id']: u for u in json.load(f)['units']}
   for cid in [151, 152, 153, 154]:
       cname = f'GPL-{cid}'
       c_occs = [o for o in occs if o['chunk'] == cname]
       c_occs.sort(key=lambda x: x.get('offset', 0))
       seen = set()
       untrans = []
       for o in c_occs:
           uid = o.get('unit_id')
           if uid and uid not in seen:
               seen.add(uid)
               if not units[uid].get('translation_zh_tw', '').strip():
                   untrans.append({'unit_id': uid, 'original': units[uid]['original'], 'whitespace': units[uid]['whitespace'], 'offset': o.get('offset', 0)})
       with open(f'scratch_test/batch_{cid}_untranslated.json', 'w', encoding='utf-8') as f:
           json.dump({cname: untrans}, f, ensure_ascii=False, indent=2)
   "
   ```
2. **撰寫翻譯並執行套用**：
   - 建立 `scratch_test/apply_gpl_151_154.py`。
   - 先行執行 Dry Run 驗證所有字串的 `leading_spaces` 與 `trailing_spaces` 100% 精確匹配。
   - 帶 `--write` 參數寫入 4 大核心目錄檔案。
3. **字型與清單編譯檢查**：
   ```bash
   python tools/cjk_localization_pipeline.py inventory
   python tools/cjk_localization_pipeline.py compile-catalog --output scratch_test/cjk_compiled.bin
   ```
4. **驗證零缺漏並更新進度文件**：
   - 驗證 `GPL-151` 至 `GPL-154` untranslated = 0。
   - 執行 `scratch_test/analyze_translation_status.py`。
   - 更新 `localization_progress.md`、`docs/名詞權威對照表.md` 與 `handoff.md`。
