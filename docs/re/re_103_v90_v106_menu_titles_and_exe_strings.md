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

## 附錄：v90～v106 逐版紀錄（2026-09-26 從 handoff.md 移入）

- **v90（2026-09-24，已確認）**：`scratch_test/cjk_display_staging_v90_fragments`
  - 對話裡殘留的 `he`、`is` 之類英文，原因是 opends 抽取時跳過了 3 字元以內的 print string，
    這些字串從來沒進 catalog。
  - 全部 250 個 GPL/MAS chunk 重新反組譯比對，漏網的共 155 處：
    - 115 處寫進 `localization/catalog/dialogue_fragment_overrides.json`，以 chunk+offset 為鍵逐處翻譯，
      空字串代表不印。
    - 40 處保留英文：GPL-20 防拷問答的比對字母，以及排版用的空白。
  - 編譯器新增 `--fragment-overrides` 選項。
  - GPL-135 的「匕首 (不)佩服你的實力」兩條譯文改了詞序。
- **v91／v92（2026-09-24，已確認）**：`scratch_test/cjk_display_staging_v92_title_y`（v91 實機顯示正常，但中文標題和第一個選項重疊 1～2px；v92 把中文標題改畫在 y=2，英文仍是 y=4，待確認）
  - 對話選單標題（`WHAT DO YOU SAY?` 等 21 條）翻成中文。
  - 標題繪製程式在 overlay `0x7D80A`：
    - 先 `strupr(ds:5504)` 轉大寫。
    - 再經 `0150:016D`（`339E:016D` formatter，`"%C%C%C%s"`）繪製，這個 formatter 不解碼 Base94。
  - 修補方式（`view_ui_layer.VIEW_UI_EXE_PATCHES` 最後兩筆）：
    - `strupr` 呼叫的 offset 改指向它自己的 `retf`（`0:39CF`）。
    - `0x7D818～0x7D83A` 換成 tag `FF81` redirect。FONT 核心的 `menu_title_entry` 會先檢查標題：
      - 含 `^`：解碼到 name-slot。
      - 純英文：自己轉大寫，照原樣傳下去。
    - 最後重新 push 原本的 formatter 參數。
  - name-slot 只有 10 格，所以**標題的相異中文字（含全形標點）不能超過 10 個**。
    本輪因此縮短了 5 條標題譯文。
  - 編譯器新增 `--translate-menu-titles`，封包會記錄 `menu_titles_translated`。
    組合包沒有 `--view-ui` 時會拒絕建置。
  - withheld 只剩 `END`、`CLOSE` 兩筆。
- **v106（2026-09-25，使用者已確認）**：`scratch_test/cjk_display_staging_v106_status_lower`
  - 使用者要求狀態字再往下 5px，離頭像框下緣 1px：y＝+26（`0x6BFB2` = `1A`），中文實際畫在 +28～+37。
- **v105（2026-09-25，位置偏高，由 v106 微調）**：`scratch_test/cjk_display_staging_v105_status_in_frame`
  - v104 的 HP 放在框內時，數字碰到頭像框、被框的顏色吃掉；三位數 HP 也會超出框。
  - 改用使用者的第二個提議：
    - HP 還原到 +38。
    - 兩個字的狀態移進頭像框底部：y＝+21（`0x6BFB2`），中文實際畫在 +23～+32；
      x 基準 1→5（`0x6BFB6`），往右 4px。
- **v104（2026-09-25，HP 被框線吃掉，改為 v105 的做法）**：`scratch_test/cjk_display_staging_v104_portrait_rows`
  - 背包畫面的單欄頭像列（overlay `0x6BEE6` 起）：
    - 頭像 y＝si×48+6；HP 原本在 +38（立即值 `0x6BF7A`），狀態原本在 +44（`0x6BFB2`）。
    - 兩行只差 6px，放不下 10px 高的中文字。
  - 當時的做法：HP 移進頭像框內（+27），狀態移到原本 HP 那一行（+38）。已由 v105 取代。
  - 其他三個畫面（USE／VIEW 等 2×2 頭像，呼叫 `0580:0066` 的 `0x7E725`、`0x87E65`、`0x89F86`）空間夠，沒有改。
  - 頭像狀態由 overlay 第 25 段第 14 個入口 `0x71D8B` 繪製：先置中，再經 `191F:0A40` 畫出。
- **v103（2026-09-25，VIEW 已確認；背包頭像空間不足，由 v104 處理）**：`scratch_test/cjk_display_staging_v103_status_layout`
  - v102 的中文顯示正常，但有兩個位置問題：
    - 背包的狀態只比 HP 低 7px，10px 高的中文字會蓋到 HP。
    - VIEW 的置中位置偏左。
  - 量寬度函式 `191F:0401`：`0x1E9F6～0x1EA06` 換成 tag `FF86` redirect，回到 IP `042A`；空指標回到 `0437`。
    中文會先解碼成字形碼，迴圈量到的就是實際畫出來的寬度。
  - `text_draw_entry`：中文的 y 座標 +2。
  - v101 的其他部分已確認：USE 切換按鈕、靈能分類、等級按鈕。
  - **待驗證**：學法術卷軸的「學習」「第3級」，使用者目前還沒有可以測試的存檔進度，之後遊玩時再確認。
- **v102（2026-09-25，中文正常、位置偏移，已由 v103 修正）**：`scratch_test/cjk_display_staging_v102_draw_text`
  - v101 實機測試時，頭像下方狀態顯示成亂碼。
  - 狀態透過 `11DC` 表取得，取法是角色資料 +0x1C 當索引；有兩處使用：
    - 背包：`0x5FD51` → `0090:0A40`，實際是常駐 `191F:0A40`（檔案 `0x1F030`）。
    - VIEW／USE：`0x71DD4`，先 strncpy，再量寬度置中。
  - `191F:0A40` 是 47 bytes 的 draw_text 包裝函式：用 `"%C%C%C%s"`（ds:0D8F）呼叫 339E:016D，不會解碼。
  - 修補方式：
    - `0x1F033～0x1F050` 換成 tag `FF84` redirect，回到 `0x1F051`。
    - FONT 核心的 `text_draw_entry`：中文就解碼成 name-slot 字形碼，英文照原樣傳下去。
  - 這個包裝函式是常駐的，其他呼叫者（`USEABLE BY:`、`HD: %d` 等）也能直接顯示中文。
  - 待觀察：`0x71DD4` 那條路徑是用 Base94 原始 bytes 量寬度，中文的置中位置可能會偏。
- **v101（2026-09-24，試驗版；頭像狀態亂碼，已由 v102 處理）**：`scratch_test/cjk_display_staging_v101_use_labels`
  - DGROUP far pointer 表（段 `4356`）引用的字串：
    - `11DC`（29 筆）指向頭像下方狀態（Okay…）、職業名、USE 切換按鈕（MAGE/CLERIC/PSlONlC）。
      切換按鈕共用職業名的字串。
    - `30FA`（4 筆）指向靈能分類（念動／精神／感應／傳送）。
    - `3112`（Kinetics 結尾的 NUL）被 push 當空字串使用，所以保留原位。
  - 學法術卷軸：LEVEL %d／選擇法術，／學習／已學會。USE 畫面也有一個 LEVEL %d。
  - `exe_text_layer` 新增兩個功能：
    - `pointer_tables`：字串搬動後，表裡的偏移跟著改（段值那個 word 有 MZ 重定位，不動）。
    - 允許多筆指向同一個字串。
  - 試驗目的：這些字串的繪製路徑還沒實機確認過（頭像狀態、切換按鈕、分類按鈕）。
  - 卷軸的 EXIT 不在 EXE：v98 已經把 EXE 唯一的 EXIT 改成「離開」，卷軸上仍是英文，應該在視窗資源（WIND）裡。
  - 已確認：USE 資訊列的「19✓ 8👢」分別是成功門檻（體質 22 − 3）和射程，
    `^`、`|` 在 FONT-100 裡是打勾和靴子圖示，保留不翻。
- **v100（2026-09-24，使用者已確認）**：`scratch_test/cjk_display_staging_v100_spell_names`
  - 法術／靈能名稱（USE 畫面下方資訊列、學法術卷軸）。v99 試驗證實這兩處的繪製路徑會解碼。
  - **譯名一律依詞彙表（智冠定名）**，使用者 2026-09-24 決定：
    - 資訊卡（SPIN）原本另有一套譯名（如 迷霧牆、解離術），共 118 張已改成詞彙表定名。
    - 其中 4 張的內文是一般用語（冰牆、魔法石、治療疾病），另外手動修正，不照替換結果。
    - NAME-1 物品名在詞彙表裡本來就另外定名（如 Ego Whip 物品＝自我之鞭），所以不改。
  - 名稱放在 DGROUP `254E～2EBA`，只由兩張資料表引用：
    - 法術表：檔案 `0x4512E`，138 筆，每筆 7 bytes，名稱位址在 +3。
    - 靈能表：檔案 `0x44F96`，34 筆，每筆 8 bytes，名稱位址在 +0。
  - 連結器合併了一些字尾，例如 ARMOR＝FLESH ARMOR 的尾巴，INVISIBILITY、SHIELD、STRENGTH、POISON 也一樣。
  - 做法：
    - `exe_text_layer.spell_block_patch` 讀 `localization/catalog/exe_spell_names.csv`（168 條）。
    - 整段重新排列，改寫 171 個表格位址，還剩 432 bytes 空間。
  - mapping 新增 10 個字，所以重建了 bank v22、對話封包 v10、資訊卡包 v4。
    舊字的 ID 和字元都沒有變。
  - 詞彙表補上召喚小型風／火／土／水元素、召喚風／火／土／水元素。
- **v98（2026-09-24，已確認）**：`scratch_test/cjk_display_staging_v98_combat_popup`
  - 戰鬥「結束角色行動」彈出框（常駐 `0x1DB1F`）：
    - 流程：先 `sprintf` 出 `END %Fs's MOVE`，再開啟 `41B4:0025` 確認框，按鈕是 GUARD／WAIT／END TURN。
    - 44 bytes 要放進五條字串，所以譯成「%Fs回合／回合／防守／等待／結束回合」。
  - 確認框的按鈕文字經 `2A1D:07FA` 設定（和對話選項相同，會解碼）。
    `4211:00B1`／`00B6` 只是計算彈出框座標，盤點腳本的「後面最近的 far call」在這裡配錯了。
  - sprintf 格式字串（`00A8:0002` = 常駐 `1D53:0002`）裡，結果會送進訊息框的 10 條也已翻譯，
    例如「%Fs升級了」「%Fs被魅惑」「找到 %u$」。
- **v97（2026-09-24，使用者已確認）**：`scratch_test/cjk_display_staging_v97_window_text`
  - v96 實機測試存檔時，提示框顯示成亂碼（Base94 bytes 被逐字畫出，`[` `{` 變成材質字形「木製」）。
  - 訊息框的文字都經過 overlay 第 25 段的 `0x7045D`（stub `0580:005C`，執行期段 `4272`）。它的流程是：
    - 字串超過 30 bytes 就在第 30 byte 寫入 NUL。
    - `strncpy(bp-28h, 字串, 31)`。
    - `strupr`（`0:2FC4`）。
    - 逐字繪製，不會解碼。
  - 修補方式：
    - `0x704AB～0x704BD` 換成 tag `FF82` redirect，回到 overlay IP `06EE` 那個沒動過的 strncpy。
    - FONT 核心的 `status_text_entry` 把中文解碼成 name-slot 字形碼，字形碼都不是 a–z，strupr 不會改到。
  - 限制：
    - 每則訊息最多 10 個相異中文字，而且不能超過 30 bytes。
    - 字形格和物品名稱共用，訊息顯示期間如果背包重畫，字形可能被換掉。
- **v96（2026-09-24，實機亂碼，已由 v97 修正）**：`scratch_test/cjk_display_staging_v96_message_boxes`
  - EXE 字串第二批：確認框與提示訊息，共 26 個區塊、約 55 條，全部寫在 `tools/exe_text_layer.py`。
  - **overlay 段號怎麼查**：執行期讀記憶體最可靠。
    - 例如 overlay 程式碼裡的 `04D0`，載入後變成執行期 `49D8`，減掉 `0x824` 就是 `41B4`。
    - `41B4` 是 overlay 第 3 段的 stub 描述區，用 ovr-map 可以解出：
      - `:0020` → `0x561D7`（請稍候）
      - `:0025` → `0x54F21`（有按鈕的確認框）
      - `:002A` → `0x5536E`（單行訊息）
    - 訊息文字經 `0580:005C` 寫進控制項 `2C06`。
    - 段號和檔案位置之間沒有固定換算關係（`0x140`→`2A1D` 只是巧合），不能直接套公式。
  - `exe_text_layer` 會自動找出所有 `push ds; push <舊位址>` 並改寫。它也會拒絕兩種情況：
    - 區塊中間有沒登記的引用。
    - 碰到 MZ 或 overlay 重定位。
  - `OKAY`（`1BD5`）的 push 被 overlay 重定位表登記，所以不搬移，只在原位譯成「好」。
  - 暫緩處理：
    - `INACTIVE CHARACTER`（`1AC1`）和 `CANCEL`（`1B7F`）也被其他路徑使用。
    - `LOAD`（5 bytes）原位放不下，`NEW`／`ADD` 也還沒處理。
  - 字型 mapping 沒有「刪」「磁」，改用「清除」「存檔空間」。
- **v95（2026-09-24，已確認）**：`scratch_test/cjk_display_staging_v95_variable_reads`
  - 使用者看到「Let's change the subject.」選項是英文。
    - 它是 MAS-99 寫進 GSTR[7] 的字串，選單用變數讀取。
    - 舊的候選清單條件把「有變數讀取引用」的單元整條排除，共 92 條（13,194 → 13,286 單元，共 13,996 處）。
  - 編譯器新增 `--all-translated`，並略過 `text:*` 引用：這種引用沒有字串資料，字串在 `string copy` 那一處。
  - 存檔改寫移到 `tools/patch_save_gstr.py`，並涵蓋 GSTR[7]。
- **v93／v94（2026-09-24，使用者已確認選項長度與是非選單正常）**：`scratch_test/cjk_display_staging_v94_yes_no`
  - **選項長度上限 49 bytes**：
    - 對話處理程式把選項存在 DGROUP `0x5537 + n×0x33` 的 51 bytes 格子裡。
      超過 50 bytes 的選項會在第 49 byte 截斷（`0x7CF1B`）。
    - 繪製時用 `strncpy(buf, 選項, 50)`（`0x7D86E`），剛好 50 bytes 就沒有 NUL，會印出堆疊垃圾。
    - 使用者看到「唾棄他」後面三個亂碼字，就是這個原因。
    - 已把 278 條選項縮短到 ≤49 bytes，也就是 2 個空白加最多 15 個中文字。
    - 編譯器遇到超長選項或標題會丟 `MenuTextTooLong`。它刻意不是 `ValueError`，
      否則會被 main 當成「跳過 chunk」吞掉。
  - **是非選單**（EXE 字串第一批）：新模組 `tools/exe_text_layer.py`。
    - `0x6B7BD` 用 DGROUP `1600`（Answer Yes or No）、`1611`（Yes）、`160E`（No，和前一句共用尾巴）組選單。
    - 對話處理程式用 `stricmp(ds:5504, ds:1F61 "answer yes or no")` 辨認是非選單，所以兩處要翻成相同的中文。
    - 「否」搬到 `160D`，`push 160Eh` 改成 `push 160Dh`。
  - **EXE 字串盤點**：
    - 用 `push ds; push <偏移>` 找引用，再看後面最近的 far call，依呼叫目標分組。例如：
      - `00A8:0002`：48 條，格式化訊息。
      - `04D0:0020/0025/002A`：約 60 條，確認框、YES/NO/CANCEL、NO MEMORY 等。
      - `0578:0070`：商店。
      - `4211:00B1`：戰鬥。
    - overlay 程式裡 far call 的段值不能用 `0x5400+段×16` 直接換算（例如 `0x140`→`2A1D`、`0x150`→`339E`），
      要到執行期確認實際函式。
