# re_103：v90～v106 選單標題、漏抽片段與 EXE 內字串中文化

> 日期：2026-09-24～25。可玩版本 `scratch_test/cjk_display_staging_v106_status_lower`，使用者已實機確認。
> 這份文件記錄這一輪的發現、修補位置，以及之後要沿用的通用做法。

## 1. 對話裡殘留的 he／is（v90）

- **原因**：opends 抽取 `ds1-dialog.json` 時，跳過了 3 字元以內的 print string，例如 `he `、`is`、`wo`、`.`，
  所以這些字串從來沒進 catalog。
- **找法**：用 `gpl-disasm --all --json` 反組譯全部 250 個 chunk，和 `dialogue_occurrences.json` 比對 offset。
  漏網的共 155 處。
- **處理**：
  - 115 處寫進 `localization/catalog/dialogue_fragment_overrides.json`，以 chunk＋offset 為鍵逐處翻譯。
    同一個片段在不同地方要不同譯法，所以不能用 unit 統一翻；空字串代表不印。
  - 40 處保留英文：GPL-20 防拷問答的比對字母，以及排版用的空白。
  - 編譯器參數：`--fragment-overrides`。

## 2. 選單標題（v91／v92）

- 標題繪製程式在 overlay `0x7D80A`。流程是先 `strupr(ds:5504)`，再經 `339E:016D` formatter（`"%C%C%C%s"`）畫出，
  這個 formatter 不解碼 Base94。
- **修補**：
  - `strupr` 呼叫的 offset 改到它自己的 `retf`（`0:39CF`）。
  - `0x7D818～0x7D83A` 換成 tag `FF81` redirect，由 FONT 核心的 `menu_title_entry` 處理：
    - 中文：解碼到 name-slot，y 改成 2（中文字形滿 10 行，y=4 會碰到第一個選項）。
    - 英文：自己轉大寫，y=4，和原版相同。
- **存檔**：全域字串（GSTR）會存進存檔，每格 42 bytes，依序是 GSTR[1] What do you say?、[2] END、[3] CLOSE、
  [4] What do you do?……舊存檔用 `tools/patch_save_gstr.py` 改寫。

## 3. 選項長度與變數引用（v93～v95）

- **選項長度上限**：選項存在 DGROUP `0x5537 + n×0x33` 的 51 bytes 格子裡，繪製時用 `strncpy(buf, 選項, 50)`（`0x7D86E`）。
  所以選項和標題編碼後最多 49 bytes，已縮短 278 條。編譯器超過上限就丟 `MenuTextTooLong`
  （刻意不是 `ValueError`，否則會被 main 當成「跳過 chunk」吞掉）。
- **變數引用**：選單以變數讀取的字串（`text:lstring`）本身沒有字串資料，舊的候選條件卻因此排除了 92 個單元。
  編譯器新增 `--all-translated`，並略過 `text:*` 引用。

## 4. EXE 字串：通用工具 `tools/exe_text_layer.py`

- `TextRegion`：一段原始 DGROUP bytes 整段重寫，字串可以在段內搬動。
  - 程式裡所有 `push ds; push <舊位址>` 自動改寫成新位址。
  - `pointer_tables`：DGROUP 內 far pointer 表（`offset:4356`）裡的位址跟著改；段值那個 word 有 MZ 重定位，不動。
  - 允許多筆引用指向同一個新字串。
- **安全檢查**：區塊中間有沒登記的引用、碰到 MZ 或 overlay 重定位、原始 bytes 不符時，都拒絕建置。
- **法術名稱**：`spell_block_patch` 讀 `localization/catalog/exe_spell_names.csv`，把 DGROUP `254E～2EBA` 整段重新排列。
  - 這段名稱只由兩張表引用：法術表（檔案 `0x4512E`，138×7 bytes，+3）和靈能表（`0x44F96`，34×8 bytes，+0）。
  - 連結器合併了一些字尾（ARMOR、INVISIBILITY、SHIELD、STRENGTH、POISON），重排後各自獨立成一條字串。
- **譯名原則**：一律依詞彙表（智冠定名），使用者 2026-09-24 決定。資訊卡（SPIN）118 張已改成同一套譯名。

## 5. overlay 呼叫目標怎麼查

- overlay 程式碼裡 far call 的段值（例如 `04D0`、`0580`、`0090`）**不能**用 `0x5400 + 段×16` 換算。
- **可靠的做法**：遊戲執行中暫停，在記憶體搜尋呼叫點的 bytes，讀出重定位後的段值，再減 `0x824` 得到載入相對段。
  - 如果結果是 stub 描述區，用 ovr-map 解出入口，例如 `41B4:0020/0025/002A`、`4272:005C/0066`。
  - 如果是常駐段，直接換算，例如 `0090:0A40` → `191F:0A40`。

## 6. 不解碼的繪製路徑與 FONT 核心 entry

name-slot 核心（`tools/cjk_name_slot_cache.asm`）新增了四個 entry，都用 tag redirect 從 EXE 跳進去：

| tag | 位置 | 用途 |
|---|---|---|
| `FF81` | overlay `0x7D818` | 對話選單標題 |
| `FF82` | overlay `0x704AB` | 視窗單行文字：訊息框、請稍候、存檔提示（`0580:005C`） |
| `FF84` | 常駐 `0x1F033` | `191F:0A40` draw_text 包裝函式：頭像狀態、物品面板標籤 |
| `FF86` | 常駐 `0x1E9F6` | `191F:0401` 字串寬度（讓置中位置正確） |

共同做法：

- 中文：先解碼成 name-slot 字形碼。字形碼都不是 a–z，所以之後的 `strupr` 不會改到。
- 英文：照原樣傳下去。

共同限制：

- 每次繪製最多 10 個相異中文字。
- 字形格和物品名稱共用；這些 entry 每次都會重新解碼，所以不會用到過期的字形。

## 7. 已翻譯的 EXE 字串（v94～v106）

- **對話**：是非選單。
- **訊息框**：約 55 條，例如存讀檔、休息、門、背包已滿。
- **戰鬥**：結束行動彈出框。
- **格式化訊息**：10 條。
- **法術與靈能**：名稱 168 條。
- **頭像與 USE 畫面**：頭像狀態、職業名、USE 切換按鈕、靈能分類、等級按鈕。
- **學法術卷軸**：學習、第%d級。尚未實機驗證。

背包頭像列（overlay `0x6BEE6` 起）的版面調整：

- HP 在 +38，狀態在 +44，兩行只差 6px，放不下 10px 高的中文字。
- 狀態移進頭像框內底部：y=+26（`0x6BFB2`），x 基準 5（`0x6BFB6`）。

## 8. 還沒處理

- **視窗資源（WIND）裡的按鈕文字**：學法術卷軸的 EXIT、背包的 DROP／SPLIT 等。它們不在 EXE，要改 RESOURCE.GFF。
- **暫緩的 EXE 字串**：
  - `INACTIVE CHARACTER`（`1AC1`）和第二個 `CANCEL`（`1B7F`）也被其他路徑使用。
  - `LOAD`、`NEW`、`ADD` 原位放不下。
- **尚未盤點的 EXE 字串**：遊戲選單（GAME MENU、MUSIC ON…）、商店（STORE、NO DEAL!、SOLD!）、
  背包下方提示列（`SELECT K'RATCHEK`、`HIT POINTS: CURRENT/MAX`）。這些都要先確認繪製路徑。
