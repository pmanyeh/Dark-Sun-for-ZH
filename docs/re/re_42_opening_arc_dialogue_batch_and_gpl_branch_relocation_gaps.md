# 開場劇情對話批次匯入與 GPL 分支重定位缺口

> 日期：2026-08-16
> 延續：`re_41_name1_fixed_record_importer_and_item_panel_renderer_gap.md`
> 狀態：翻譯與三個真實 relocation bug（`0x48`／`0x29`／`0x14` 自我參照）已修復並
> 實機驗證——**競技場戰鬥觸發卡死已解決**，戰鬥結束後續劇情也能正常繼續。
> 仍有一個已知但尚未修復的次要缺口：GPL-4 有一個指向 GPL-2 的**跨 chunk** `0x14`
> 呼叫，其目標未隨 GPL-2 的位移調整（見第 7 節），影響範圍與時機待確認。

## 1. 目標

依交接備忘錄第 12.5 步「擴大正式文本翻譯」，選定一個有邊界、經實機確認為遊戲真實
開場的劇情段落，作為對話系統的第一個大批量翻譯試點。

## 2. 開場故事線識別（GPL-2~5）

`dialogue_occurrences.json` 裡的 GPL chunk 編號**不是**按遊戲流程排序的（第一次
以為「編號小＝早期」是錯的，`GPL-1` 其實是完全無關的 A'poss 神殿支線）。完整讀完
每個候選 chunk 全文後確認：

- `GPL-2`（119 行）：競技場開場公告，含已匯入的 Celgor 段落；
- `GPL-3`（40 行）：觀眾反應＋逃獄觸發；
- `GPL-4`（112 行）：逃獄過程中與獄卒／盟友 Garn 的對話；
- `GPL-5`（158 行）：救出囚犯 Semyon、引出「面紗聯盟」支線。

四個 chunk 合計 429 個 occurrence、327 個不重複翻譯單元，是一段連貫、經確認的
真實開場敘事。

## 3. 權威詞彙表

新增 `localization/proper_noun_glossary.json`，記錄所有專有名詞（人名／地名／
陣營）與反覆使用的關鍵詞（如「the pens」→獸欄、「gladiator」→角鬥士）的統一譯法，
翻譯任何新批次前先查詢、翻譯完立刻回寫，避免同一名詞在不同段落譯法不一致。

## 4. 三個匯入限制（依序發現）

### 4.1 字元超過 4-bank 容量 → 擴充 5-bank runtime

327 筆翻譯用到 353 個新字元，加上既有 923 個，共 1276 個，超過 4×256=1024 的
容量上限。`tools/patch_dsun_scratch_cache.py`／`tools/cjk_scratch_cache.asm` 已
參數化 `bank_count`（原本寫死 4），並將 bank 檔名從 `C0.BIN` 縮短為 `C0`（DOS
不需要副檔名），因為 `NAMES` 表格與 resolver stub（`COMMON`，`36AA:5420`）之間
只有 42 bytes 可用，5 個帶副檔名的檔名表放不下，縮短檔名後可放到 8 個 bank
（`36AA:53F6..541E`，`COMMON` 之前）。新增測試驗證 5-bank 組譯與 patch 皆正確。

### 4.2 TEXT-gstring 標籤（Dag／Halton／Garn／Magramar）

這四個反覆出現的角色標籤（`Dag` 50 次、`Halton` 35 次、`Garn` 11 次等）在
GPL-2~5 裡的每一次出現，`occurrence.source` 都是 `text:gstring`，不是
`inline`/`compressed`——代表它們是從 `GPLDATA.GFF` 的 TEXT 字串表讀取的，
不是內嵌壓縮字串。`compile_gpl_dialogue_patch.py` 完全無法處理這種來源，
本次已排除、暫時維持英文。這跟 `localization_manifest` 裡 60 筆 `text`
類別（Deestan、Garn、Dag...）是同一套機制，目前**沒有任何匯入器**能寫入
TEXT chunk 字串表，是後續需要的第三種匯入器。

### 4.3 多選項對話共享同一個指令位址

`gpl menu`（`0x48`）指令把同一個選單的所有選項文字，全部編碼在**同一條指令**
裡；`dialogue_occurrences.json` 對這些選項的 `offset` 記錄的是整條指令的起始
位址，不是各自獨立的位址。`compile_gpl_dialogue_patch.py` 目前假設「一個位址
只對應一筆翻譯」，選到同一位址的多筆翻譯會直接互相覆蓋、觸發
`multiple dialogue edits target the same instruction offset` 錯誤。本次排除
了 74 筆屬於此類的選項文字（維持英文），匯入剩餘 248 筆。若要翻譯選項文字本身，
`relocate_json_strings` 需要先擴充成「一個位址可接受多筆編輯」，逐一比對選項
內文才能正確替換——這是比目前更大的架構調整，本次未做。

## 5. 兩個真實的分支重定位 bug（已修復）

排除上述三個「無法匯入」的情況後，剩餘 248 筆順利匯入、通過既有的全容器驗證，
但實機測試發現：物品說明彈窗以外，**點選任何多選項對話的選項後，遊戲完全卡住
不動**。深入排查後找到兩個 `compile_gpl_dialogue_patch.py` 既有邏輯從未涵蓋的
真實 bug（不是本次新引入，是先前批次規模太小、剛好沒踩到）：

### 5.1 `gpl menu`（`0x48`）內嵌跳轉目標未重定位

每個選項在指令參數列裡是 `(選項文字, 跳轉目標, 旗標)` 三個一組，`menu name`
表頭之後重複到指令結尾。既有的 `BRANCH_PARAMETER` 只認得幾種標準分支 opcode
（`0x12/0x13/0x27/0x3E/0x3F/0x63/0x64`），完全不知道 `0x48` 的參數列裡也藏著
跳轉目標。當選單指令**之前**的內容被翻譯改變長度、指令整體位移後，選單指令
自己的起始位址有跟著更新，但**選項內嵌的跳轉目標值沒有**，導致點擊後跳到一個
已經錯位、可能落在指令邊界外的地方。

修復：`relocate_json_strings` 新增對 `0x48` 的特別處理，在跳過表頭 expression
後，以 3 為一組處理每個選項，重定位第二個 expression（跳轉目標），沿用既有的
`offset_map` 機制。新增 `tests/test_gpl_dialogue_importer.py::
test_json_edit_relocates_menu_entry_targets` 驗證。

### 5.2 `gpl orelse`（`0x29`）分支目標同樣缺漏

系統性審核 OpenDS 的完整 opcode 表（`vendor/opends/tools/gpl-disasm/src/lib.rs`
`PARAM_COUNTS`）後，另外發現 `0x29`（`gpl orelse`，單一 `immediate14` 參數）
也不在 `BRANCH_PARAMETER` 裡，同樣的問題。已加入 `BRANCH_PARAMETER = {0x29: 0}`，
新增對應測試驗證。

### 5.3 排除的誤判：trigger 類 opcode（`0x6E`／`0x6F`／`0x70`）

同一輪審核裡，`0x6E`（talktotrigger）、`0x6F`（noorderstrigger）、`0x70`
（usewithtrigger）一開始也被懷疑帶有同 chunk 跳轉目標（它們的 leading
`immediate14` 參數數值巧合地符合某個真實指令位址）。**進一步查證後推翻**：
這些數值（例如 `100`、`74`）在完全不同長度、不同內容的 chunk 裡重複出現，
不可能是真的同 chunk 相對位址，而是固定的門檻常數（距離／優先度之類）；真正的
目標更可能藏在參數列尾端的 `immediate_name`／`complex_access`／
`variable(gname)`（符號參照，不需要同 chunk 重定位）。已刻意不把這幾個 opcode
加進 `BRANCH_PARAMETER`，並在程式碼註解記錄判斷依據，避免未來誤加。

修復並用 v19（`scratch_test/cjk_display_staging_v19_orelse_fix`）重新驗證：
反組譯確認 GPL-2/3/4/5 所有 `0x48` 與 `0x29` 目標，重定位後都精確落在合法指令
邊界上，四個 chunk 的 `aligned`／`bytes_consumed==total_bytes` 也都正確。

## 6. 戰鬥觸發卡死的真正根因：`0x14`（gpl global sub）自我參照未重定位

v19 實機測試：對話段落順序、選單互動都恢復正常，但遊戲仍在「馴獸師：放出你的
獸群！」之後卡死——預期的戰鬥沒有發生，直接跳到戰鬥結束後才該出現的「角鬥士
們：回到獸欄去療傷」，玩家無法繼續、也無法撤退。

### 6.1 排除法

1. 用 v15（完全沒有本次任何改動）以相同方式開新遊戲、走到同一個點，**戰鬥
   正常觸發**——證明問題出在本次的 GPL-2 patch，不是測試環境或存檔狀態。
2. 把翻譯前後的 GPL-2 完整反組譯 IR 逐指令結構化比對（opcode 序列、
   非字串／非跳轉參數逐一比對），結果完全一致（0 處非預期差異）——證明
   `relocate_json_strings` 對「已知」的分支／menu 重定位邏輯本身沒有錯，
   問題出在某個**還沒被涵蓋**的內嵌位址。

### 6.2 根因

`gpl global sub`（`0x14`）的參數是 `(offset, chunk_id)`，語意上是「呼叫指定
chunk 裡的一段子程式」，多數情況下是**跨 chunk**呼叫，本來就不受單一 chunk
重定位影響，先前因此把它整個排除在外。但 GPL-2 內部實際有兩處 `0x14` 呼叫
（offset 2887、5307）的目標 `chunk_id` 剛好等於**自己所在的 chunk（2）**——
也就是用「跨 chunk」的呼叫機制，呼叫自己 chunk 內的子程式。這兩處呼叫的
`offset` 參數（原始值 5367）在本次翻譯後從未被調整，因此指向的是舊、已經
位移過的位置，執行到那裡等於落在錯誤的位元組上，導致後續邏輯（設定
`gflag17`／`gflag18` 等旗標的路徑）沒有正確執行，讓「已完成，直接回獸欄」
的捷徑條件被誤判成立。

### 6.3 修復

`compile_gpl_dialogue_patch.py`／`relocate_json_strings` 新增 `chunk_id`
參數；遇到 `0x14` 時，只有當它的 `chunk_id` 參數等於**目前正在處理的 chunk**
才視為同 chunk 引用並重定位其 `offset` 參數（沿用既有 `offset_map`），真正
跨 chunk 的呼叫維持原樣不動。新增
`tests/test_gpl_dialogue_importer.py::
test_json_edit_relocates_self_referencing_global_sub` 同時驗證兩種情形。

修復後用 v20（`scratch_test/cjk_display_staging_v20_global_sub_fix`）重新
匯入、實機驗證：**戰鬥正常觸發，戰鬥結束後續劇情也能正常繼續**（含逃獄段落
的分支對話）。

## 7. 已知但尚未修復：跨 chunk `0x14` 引用的一致性缺口

反組譯掃描發現 GPL-4 offset 1956 有一個真正的跨 chunk `0x14` 呼叫，目標是
`(offset=5367, chunk_id=2)`——即呼叫 GPL-2 的舊 offset 5367。因為 GPL-2 本身
已被本次翻譯整體位移，該位置現在的真實內容已經搬到 5313；但這個修正只發生在
**處理 GPL-2 自己**的時候，GPL-4 是獨立處理的另一個 chunk，它記錄的目標值
不會自動跟著更新。

目前的匯入器架構是逐 chunk 獨立呼叫 `relocate_json_strings`，沒有「先算出
所有被觸碰 chunk 的位移量，再統一修正所有跨 chunk 引用」的機制。要修好這個
class 的問題，需要：

1. 先對所有要匯入的 chunk 各自跑一次 relocation，蒐集每個 chunk 的
   `offset_map`；
2. 再對每個 chunk 裡「目標 chunk 也在本次匯入範圍內」的 `0x14` 呼叫，用
   對應目標 chunk 的 `offset_map` 修正其 `offset` 參數；
3. 對「目標 chunk 不在本次匯入範圍內」的呼叫，維持現狀不動即可（目標 chunk
   沒被動過，offset 仍然有效）。

這次的重現案例（競技場戰鬥卡死）發生在進入逃獄橋段（GPL-4）之前，不受這個
缺口影響，因此未在本次修復範圍內。**下一個翻譯批次涵蓋到 GPL-4 內容時，
必須先處理這個缺口**，否則玩家從 GPL-4 呼叫回 GPL-2 的邏輯可能出現與本次
相同類型的卡死。

## 8. 目前狀態

- **v20**（`scratch_test/cjk_display_staging_v20_global_sub_fix`）已實機確認
  競技場開場、戰鷟觸發、戰後劇情銜接全部正常，是目前 GPL-2~5 對話翻譯的
  最新、功能正確版本，但**尚未做完整全程回歸**（未逐段落走完整個 GPL-2~5，
  也還沒排除第 7 節的跨 chunk 缺口是否在後續內容中發威），先不升格為正式
  checkpoint，仍需更多實機測試。
- **v15**（`scratch_test/cjk_display_staging_v15_preferred_complete_text`）
  仍是目前唯一經過完整回歸確認的可玩版本。
- v16（NAME-1 物品名稱）、v17／v18／v19（開場對話中間版本）已被 v20 取代，
  不建議再使用；v16 的物品面板 renderer 缺口（`re_41`）仍然獨立未解決。
- 已確認可安全沿用的成果：
  - `tools/compile_gff_name_records.py`（NAME-1 匯入器）與 321 筆物品翻譯；
  - 5-bank runtime 支援（`bank_count` 參數化、縮短檔名）；
  - `compile_gpl_dialogue_patch.py` 的 `0x48`／`0x29`／`0x14`（自我參照）
    重定位修復；
  - `localization/proper_noun_glossary.json` 權威詞彙表；
  - 248 筆已翻譯且重定位正確的 GPL-2~5 對話文字。
- 自動測試：38 項全數通過（含 `test_json_edit_relocates_menu_entry_targets`、
  `test_json_edit_relocates_orelse_branch_target`、
  `test_json_edit_relocates_self_referencing_global_sub`）。

## 9. 新發現：逃獄選項選完後，走到出口沒有反應

用 v20 做完整回歸測試時發現：實機依序選過 GPL-4「衝向西側出口」相關的逃獄
對話選項後（已確認確實選過，不是還沒推進到那一步），走到出口沒有觸發任何
場景切換或提示——相較之下 v15（未經本次任何修改）在對應情境下會正確顯示
「This corridor leads down to the slavepens. Do you wish to continue?」。

### 9.1 已排除的假設

1. **地圖觸發表（`ETAB`）內嵌 GPL chunk 位址參照。** 遊戲共有 33 個區域檔
   （`RGN02.GFF`～`RGN2D.GFF`、`RGNFF.GFF`），各自包含 `GMAP`（通行/高度）、
   `RMAP`（地圖）、`TILE`（圖磚）、`ETAB`（放置在區域內的實體表）。假設
   `ETAB` 直接以 `(chunk_id, offset)` 或 `(offset, chunk_id)` 形式儲存指向
   GPL-3 舊位址（1985，`0x07C1`）的參照，逐一掃描全部 33 個 `ETAB` chunk
   搜尋對應的 4-byte 樣式（兩種位元組順序都試過），**完全沒有命中**，此假設
   不成立（或儲存方式不是簡單的直接位移值）。
2. **GPL-4「衝向西側出口」選項本身缺漏內嵌位址。** 檢視選項對應的後續指令
   （offset 4401 起）只是設定 `lflag 21`／`gflag 22` 為 1，再繼續印出後續
   對白（「拚死一戰！」），沒有看到任何呼叫／跳轉類指令，看起來不是本次已知
   的三種重定位缺口（`0x48`／`0x29`／`0x14`）造成的。

### 9.2 目前推測（未證實）

`gflag`（全域旗標）很可能是連結「劇情選擇」與「地圖通行條件」的橋樑——
選擇逃獄選項時設定的 `gflag22`，可能被 `GMAP`（通行資料）或 `ETAB`
（實體/觸發表）以某種尚未理解的方式查詢，決定該出口格子當下是否可通行／
觸發事件。這整套「劇情旗標 ↔ 地圖通行」的關聯機制目前完全未逆向過，需要
從頭研究 `GMAP`／`RMAP`／`ETAB` 的二進位格式，才能判斷本次翻譯是否真的
影響了它（例如透過旗標編號的間接參照，而非直接的 chunk 位址）,或者這其實
是與翻譯無關的另一個問題。

**這是一次全新、獨立的逆向工程調查，範圍未知，不要在沒有更多線索前貿然嘗試
修改 `GMAP`／`RMAP`／`ETAB`。** 建議下次調查方向：

1. 先確認是哪一個 `RGN*.GFF` 對應競技場／逃獄場景（可能需要在遊戲載入該
   場景時，用 DOSBox-X-AI 觀察記憶體中哪個區域檔被讀入，或搜尋遊戲記憶體
   裡目前載入的 `RMAP`/`GMAP` 資料，反查來源檔案）；
2. 對照 v15（正常）與 v20（卡住）在這個出口互動當下的記憶體／暫存器狀態，
   找出兩者第一個出現差異的地方；
3. 或者直接對 `gflag22` 的讀取／寫入位置設記憶體監看點，觀察它何時被讀取、
   讀取後執行了什麼判斷。

## 10. 下一步建議

1. **優先：地圖通行機制調查（第 9 節）。** 這是目前唯一已知會讓遊戲卡住、
   但尚未修好的問題。
2. 用 v20 完整走一輪 GPL-2~5 涵蓋的劇情，確認沒有其他卡死點，特別留意會不會
   踩到第 7 節的跨 chunk `0x14` 缺口；
3. 全程無誤後，才將 v20 升格為新的正式 checkpoint；
4. 修好第 7 節的跨 chunk `0x14` 一致性缺口，再繼續擴大翻譯到 GPL-4 之後的
   內容；
5. 物品面板 renderer（`re_41`）與 `MORE` 變色 polish 仍然獨立待辦。
