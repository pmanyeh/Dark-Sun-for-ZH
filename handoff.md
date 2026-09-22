# 《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands) 繁中化交接指南 (handoff.md)

> **產生時間**：2026-09-21 23:01  
> **交接目的**：為下一輪重開 Session 的 AI 助手提供完整無縫的專案背景、歷史數據、技術規範、標準操作 SOP 與接續目標，確保繁中在地化推進不中斷。

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
