# OpenDS 對話回寫突破與全遊戲本地化目錄

> 日期：2026-08-13  
> 前置文件：`re_05_gpl_text_decompressor_reverse_engineering.md`、`re_07_verified_gpl_loop_and_dosbox_setup.md`、`re_09_bpm_hook_and_resident_gff_loader_trace.md`

## 1. 本日結論

今天跨過了中文化工作中最關鍵的一道門檻：我們不只可以從 `GPLDATA.GFF` 讀出 GPL 對話，也已經完成一次實際的修改、重新封裝與遊戲內顯示驗證。

測試時將遊戲開頭 Celgor 的英文句子改為 `TEST DAY...`，重新封裝測試用的 `GPLDATA.GFF` 後，由 DOSBox-X 啟動遊戲，畫面確實顯示修改後的文字。這證明目前 OpenDS 路徑至少已打通以下閉環：

```text
GPLDATA.GFF
    → 解出 GPL/MAS 腳本與字串
    → 修改文字
    → 重新封裝 GFF
    → DOSBox-X 實機顯示
```

因此，先前對 GPL 壓縮格式、載入流程與記憶體解壓縮函式的逆向研究仍然有價值，但已不再是英文對話抽取與等長英文回寫的唯一阻塞點。DOSBox-X Debugger 接下來主要用於處理靜態工具無法判定的動態字串，以及 Big5、字型和排版問題。

## 2. 今天完成的工作

### 2.1 對話完整抽取與去重

OpenDS 從 GPL/MAS 腳本保留了 17,699 個對話出現位置。依 namespace 內的完整原文精確去重後，得到 13,295 個對話翻譯單位。

目前的資料分成兩層：

- `localization/catalog/dialogue_units.csv`：譯者使用的主要工作表，一段相同原文只翻譯一次。
- `localization/catalog/dialogue_occurrences.csv`：保留每一次腳本引用的位置，可從 `unit_id` 回查原始 chunk、offset、opcode、text ID 與其他腳本資訊。

JSON 版本另外保留巢狀位置資料，以及動態字串可能的寫入來源。去重時沒有裁掉原文前後空白；空白資訊會保留下來，避免之後回寫時破壞腳本語意或版面。

17,699 個位置中，有 17,674 個已能靜態連結到確定文字。另有 25 個 `LSTR` 動態字串暫時不能唯一決定內容，但每一筆都已記錄可能的 writer，沒有完全失去追蹤線索。

### 2.2 建立全遊戲 localization manifest

已將 GPL 對話以外的主要文字來源整合到同一份 manifest：

| 類別 | 去重後單位 | 說明 |
|---|---:|---|
| `dialogue` | 13,295 | GPL/MAS 對話與腳本文字 |
| `spin` | 178 | 法術名稱 |
| `name` | 296 | 物件與名稱資料 |
| `text` | 60 | RESOURCE 內文字資源 |
| `merr` | 27 | 訊息／錯誤文字 |
| `etme` | 1 | 建置或匯入資訊，暫列為非玩家文字 |
| `exe_ui_candidate` | 369 | 疑似 EXE UI 字串，待確認 |
| `exe_format_or_ui` | 54 | 格式或 UI 候選字串，待確認 |
| `exe_diagnostic` | 40 | 診斷字串，待確認 |
| `exe_string_candidate` | 193 | 其他 EXE 候選字串，待確認 |

合計為 14,513 個唯一單位，目前有 13,854 個被標為可翻譯。既有的 SPIN 與 NAME 翻譯已帶入 466 個去重單位。

GFF 內重複內容會共用一個翻譯單位，但仍保留所有資源位置。例如 328 個 NAME 出現位置去重為 296 個單位；180 個 SPIN 出現位置去重為 178 個單位。

另外確認 SPIN 的實際資源 ID 並非連續的 1–180，而是 1–172、249–255 與 1000。現有翻譯涵蓋 1–172，其餘 8 筆仍待處理。

### 2.3 EXE 字串的處理界線

`DSUN.EXE` 目前使用保守的 NUL 結尾 ASCII 掃描規則，留下 725 個出現位置、656 個去重候選，另排除 292 段明顯不合適的 printable runs。

這些結果仍可能混有內部符號、格式樣板或看似文字的資料，因此全部標記為 `needs_review` 且 `translate=false`。它們已納入總目錄以免遺漏，但目前不能視為 656 個已確認的玩家 UI 字串。

## 3. 產出與重現方式

主要成果位於：

- `localization/catalog/dialogue_units.csv`
- `localization/catalog/dialogue_occurrences.csv`
- `localization/catalog/localization_manifest.csv`
- `localization/catalog/dialogue_units.json`
- `localization/catalog/dialogue_occurrences.json`
- `localization/catalog/localization_manifest.json`

重新產生目錄：

```powershell
python tools\build_localization_manifest.py
```

產生器會讀回 CSV 中非空的 `translation_zh_tw` 與狀態，因此正常重新掃描不會清掉已填譯文。CSV 使用 UTF-8 BOM，可直接以 VS Code、Excel 或 LibreOffice 開啟。

目前驗證結果：

- 三份 CSV 的資料列數分別為 13,295、17,699、14,513。
- 所有 `unit_id` 唯一。
- 所有已解析 occurrence 都能指向有效的翻譯單位。
- 25 個未解析動態字串均保留候選 writer。
- manifest 保存來源檔案的 SHA-256，方便日後確認是否對同一版本的遊戲資料操作。
- 測試修改只使用測試副本，Steam 原始遊戲檔未被覆寫。

## 4. 這項突破改變了什麼

在此之前，最大的疑問是「即使找到文字，是否真的能重新封裝並被遊戲接受」。現在答案已是肯定的，至少對已測試的英文 GPL 對話成立。

接下來的核心風險已從「能不能取出與放回」轉為：

1. 中文 Big5 雙位元組會不會被腳本長度、token 或字串走訪邏輯誤判。
2. 遊戲字型與 renderer 是否能正確映射並繪製中文字形。
3. 中文譯文變長後，對話框換行、分頁與選項排版是否安全。
4. EXE UI、動態 `LSTR` 與其他非 GPL 文字是否需要不同的回寫機制。

## 5. 下一步計畫

### 第一階段：建立最小 Big5 回寫實驗

先挑選已在遊戲開頭驗證過的 Celgor 句子，製作一個極短的繁體中文測試字串。回寫工具必須以 bytes 為長度基準，而不是 Python 字元數，並先在遊戲測試副本操作。

測試時記錄：

- 封裝是否成功、GFF 是否仍可重新解析。
- 遊戲是否正常載入該段對話。
- Big5 bytes 是否完整到達顯示緩衝區。
- 畫面結果是正確中文字、亂碼、空白方塊，還是造成腳本錯位。

### 第二階段：確認字型與字元映射

若 Big5 bytes 已進入遊戲但不能正確顯示，下一個焦點是 `FONT` 資源與繪字函式。需要建立可重複的最小中文字集，先只包含測試句所需字形，確認：

- 遊戲採用單位元組索引、雙位元組碼頁，或自訂字元表。
- 字寬是否固定，以及中文字是否需要兩格寬。
- 換行和游標前進是依 byte 還是 glyph 計算。

DOSBox-X Debugger 在此階段仍有必要，可用來觀察字串緩衝區、renderer 輸入與 glyph lookup。

### 第三階段：建立安全的批次翻譯與回寫流程

Big5 顯示路徑驗證後，再把 `dialogue_units.csv` 當作翻譯主表，依 `dialogue_occurrences.csv` 展開至所有腳本位置，並加入以下自動檢查：

- Big5 可編碼性與禁用字檢查。
- byte 長度、終止符、前後空白與控制碼檢查。
- 對話框行寬與可能溢位提示。
- 重複 unit 一致性。
- 封裝後重新抽取比對，以及原始檔／測試檔 SHA-256 檢查。

### 第四階段：補齊非對話文字

依優先度處理：

1. 人工分類 656 個 EXE 候選，找出真正的選單、按鈕與系統提示。
2. 完成 SPIN 尚缺的 8 個資源 ID，複核 NAME、TEXT 與 MERR。
3. 針對 25 個動態 `LSTR` 使用靜態 writer 分析或 DOSBox-X 執行追蹤。
4. 分別驗證 RESOURCE、GPLDATA 與 EXE 字串的回寫方式。

## 6. 下一個明確里程碑

下一個里程碑不是立即翻譯全部 13,295 段對話，而是完成一個可重複的「單句繁體中文 round-trip」：

```text
manifest 譯文
    → Big5 編碼與長度檢查
    → GPL/GFF 回寫
    → 重新抽取一致性驗證
    → DOSBox-X 遊戲內正確顯示中文字
```

只要這個最小閉環成立，就能把目前的大量文本目錄安全地轉化為真正可持續進行的中文化管線。
