# 開場劇情對話批次匯入與 GPL 分支重定位缺口

> 日期：2026-08-16
> 延續：`re_41_name1_fixed_record_importer_and_item_panel_renderer_gap.md`
> 狀態：翻譯與兩個真實 relocation bug 已修復並驗證，**但戰鬥觸發仍會卡死，尚未解決**

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
`variable(gname)`（符號參照，類似 `0x14 gpl global sub` 的跨 chunk 呼叫，不需要
同 chunk 重定位）。已刻意不把這幾個 opcode 加進 `BRANCH_PARAMETER`，並在程式碼
註解記錄判斷依據，避免未來誤加。`0x14` 本身也明確排除（跨 chunk 呼叫，天生不受
單一 chunk 重定位影響）。

修復並用 v19（`scratch_test/cjk_display_staging_v19_orelse_fix`）重新驗證：
反組譯確認 GPL-2/3/4/5 所有 `0x48` 與 `0x29` 目標，重定位後都精確落在合法指令
邊界上，四個 chunk 的 `aligned`／`bytes_consumed==total_bytes` 也都正確。

## 6. 尚未解決：戰鬥觸發卡死

v19 實機測試：對話段落順序恢復正常（不再有段落被錯誤地黏在一起），選項選單
本身也能正常互動，**但遊戲仍在「馴獸師：放出你的獸群！」之後卡死**——預期
應該觸發的戰鬥沒有發生，直接跳到戰鬥結束後才該出現的「角鬥士們：回到獸欄去
療傷」提示；此時玩家無法繼續戰鬥、也無法撤退回休息室，遊戲整個卡住。

靜態反組譯確認這段是一連串隨機播報用語選擇鏈（多個 `0x27 ifcompare` 依序判斷，
挑一句公告詞），本身邏輯正確；但尚未追到「真正觸發怪物釋放與 `gpl fight`
（`0x35`）」的實際路徑，也還沒排除是否有第三個未涵蓋的內嵌跳轉 opcode，或是
其他機制（例如某個 lflag 狀態被間接影響）。DOSBox-X 測試視窗在追查過程中被
使用者意外關閉，未能用即時除錯器（見 `re_41` 第 15 節連線方式）進一步鎖定。

**這是下一個 session 最優先要解決的問題**，且範圍可能比目前找到的兩個 bug
更廣——建議：

1. 重啟 v19，走到「Monster Trainer: release your horde!」出現的當下，透過
   DOSBox-X-AI 對 `0x35 gpl fight`／怪物生成相關 GPL 呼叫下中斷點，實際追蹤
   哪一段邏輯被跳過或跳錯；
2. 或者更保守地，先只匯入 GPL-2~5 裡**不含任何 `0x48`／`0x29`／戰鬥觸發鄰近
   內容**的段落（例如單純的 GPL-5 對話段），縮小範圍逐步擴大，避免一次踩進
   整個未知的戰鬥觸發鏈。

## 7. 目前狀態

- **v15**（`scratch_test/cjk_display_staging_v15_preferred_complete_text`）
  仍是唯一建議的可玩版本，完全不受本次任何變動影響。
- v16（NAME-1 物品名稱）、v17／v18／v19（開場對話）皆已建置成功、通過靜態
  驗證與自動測試，但**都不建議實際遊玩**——v16 物品面板顯示亂碼（`re_41`），
  v17~v19 會在競技場戰鬥觸發處卡死。
- 已確認可安全沿用、不受影響的成果：
  - `tools/compile_gff_name_records.py`（NAME-1 匯入器）與 321 筆物品翻譯；
  - 5-bank runtime 支援（`bank_count` 參數化、縮短檔名）；
  - `compile_gpl_dialogue_patch.py` 的 `0x48`／`0x29` 重定位修復；
  - `localization/proper_noun_glossary.json` 權威詞彙表；
  - 248 筆已翻譯且重定位正確的 GPL-2~5 對話文字（已寫入
    `localization/catalog/dialogue_units.csv`／`.json` 與
    `localization_manifest.csv`／`.json`，`status=translated_unreviewed`）。
- 自動測試：37 項全數通過（含本次新增的 `test_json_edit_relocates_
  menu_entry_targets`、`test_json_edit_relocates_orelse_branch_target`）。

## 8. 給下一個 session 的具體重現步驟

```text
1. 啟動 scratch_test/cjk_display_staging_v19_orelse_fix（或依 re_41/HANDOFF
   的啟動方式重建同等版本）；
2. 開新遊戲（不是讀檔），走到競技場開場；
3. 對話會正常顯示到「馴獸師：放出你的獸群！」；
4. 預期應該觸發一場戰鬥，實際上直接跳到「角鬥士們：回到獸欄去療傷」；
5. 此時任何選項／點擊都無法讓遊戲繼續，也無法撤退。
```
