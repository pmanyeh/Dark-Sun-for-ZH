# v61：物品資訊面板 AC:／PSI: 中文標籤候選版

> 日期：2026-09-16
>
> 承接 `re_82` 的交接整理。本文件同時修正 `re_82` 記錄的基準版本：實際使用者
> 已驗收的版本是 **v60**（`re_73`，裝備格 hover 名稱解碼），不是 v58b；
> v59（互動修復）與 v60 都已通過使用者實機驗證。
>
> **狀態更新**：v61 已由使用者與 Claude 在真實 DOSBox-X 上共同驗證。第一次
> 驗證時，按物品欄快速鍵 `I` 會讓整個 DOSBox-X 閃退；已定位並修正
> `psi_label_entry` 的堆疊重複推入 bug（見第 9 節），修正後在物品欄實機
> 確認「靈能: 27/27」「防禦: 8」正確顯示、六項能力值與武器傷害列不受影響、
> 不再閃退。

## 1. 本輪範圍

依 `re_82` 第 4 節建議，從 `re_68` 列出但尚未實裝、且**沒有已知技術阻礙**的
固定字串開始：`AC: %2d`、`%C%C%CPSI:`、`Bone`。

實際完成 **AC:** 與 **PSI:** 兩項，產出 **v61 候選版**（尚未實機驗證）。
**Bone** 的消費端程式碼本輪未定位完成，不在這版範圍內（見第 5 節）。

在動工前，先重新查證 `re_72` 建議的下一步（VIEW CHARACTER 下半部性別／
種族／陣營／職業）：靜態反組譯 `0x8A1AC`～`0x8A20E` 發現這些欄位其實是透過
**同一個角色資料記錄指標**（`es:[0x25B]` 索引、`stride=0x47`、基底表
`DS:[0x1661]/[0x1663]`）分派給不同的格式化進入點（`0x538:0x2a` 性別／種族、
`0x538:0x2f` 陣營、經 `0x8A8B4` 包裝呼叫 `0x580:0x84` 的職業），是 enum
查表機制，不是固定字串——比 `re_72` 原先記錄的複雜度更高，因此改採
`re_82` 的另一條建議路徑（本文件）。

## 2. AC: 與 PSI: 的消費端

物品資訊面板（`re_68` 的固定介面）中：

- **AC:**（檔案 offset `0x497C0`，字串 `"AC: %2d\0"`）先在 `0x64D70` 附近的
  子函式內以 `sprintf`（`lcall 0xA8:0x2`）格式化到堆疊區域
  `ss:[bp-0x50]`，再於 `0x64D8A`～`0x64DAF` 把該緩衝區位址與座標／顏色
  常數一起交給共用繪字呼叫 `lcall 0x150:0x16D`。
- **PSI:**（檔案 offset `0x4A3AC`，字串 `"%C%C%CPSI:\0"`）不經過
  `sprintf`，直接在 `0x6F60E`～`0x6F629` 把字串位址、座標與顏色常數交給
  同一個 `lcall 0x150:0x16D`。

兩者都落在既有 `ITEM_LINE_ADVANCE_PATCHES`（`plan_name_slot_consumers.py`）
已經修補過列距的同一個 overlay 函式內，屬於物品欄能力值／PSI／AC 面板的
既有可信賴區域。

## 3. 設計：只覆蓋差異，不重寫整個呼叫

- **AC:** `"AC"` 與草稿 `"防禦"` 都恰好是 2 個位元組寬（1 個中文字＝1 個
  transport code 位元組）。因此只覆寫 `sprintf` 產生的緩衝區前 2 bytes，
  `":"`、`" "` 及數字本體完全不動，原始 `lcall 0x150:0x16D` 呼叫也完全
  不修改——只在 `sprintf` 呼叫之後、原繪字呼叫之前插入重新導向。
- **PSI:** `"%C%C%C"` 是繪字函式自身認得的顏色控制序列，不是可翻譯文字，
  維持原樣寫死在一個新的 FONT-local 緩衝區開頭；`"PSI:"`（4 bytes）換成
  解碼後的 `"靈能:"`（3 bytes：2 個 transport code + 冒號）。由於可替換的
  最小片段（`push ds; push 0x1a4c; push 0x4500ec; push dword[0x11a4]`，
  14 bytes）小於共用重新導向 stub 的 22-byte 下限，改為往前多納入一個
  `push` 湊到 22 bytes；**刻意不把片段往後延伸進 `lcall 0x150:0x16D`
  本身**，因為該遠呼叫的 segment word（`0x150`）是 overlay relocation
  目標，若覆寫會在載入期被錯誤修補（本輪第一次嘗試就是這樣被
  `verify_overlay_relocations` 擋下，見第 6 節）。

兩者都復用既有的 `ability_text` macro／`ability_sources` 兩三元組解碼機制，
但用**獨立的 tag range**（`0xFFF6`／`0xFFF7`，透過新的 `.ifdef fixed_labels`
區塊），不去擴充現有 `ability_sources`（`0xFFF0`–`0xFFF5`）。這是刻意的：
`assemble_name_slot_cache` 對 `ability_ids` 的長度驗證是寫死 12
（`len(ability_ids) != 12`），若直接擴充該陣列，會改變 v57～v60 每一版
FONT 核心的位元組內容，讓它們各自的 hash 驗證全部失效。新增 `label_ids`
（4 個 ID，`ac_label_id_0/1`、`psi_label_id_0/1`）是完全獨立、向後相容的
擴充參數。

外層進入點 dispatch tag 用 `0xFFE9`（AC）／`0xFFEA`（PSI），與既有
`0xFFEB`–`0xFFED`（VIEW／abilities）、`0xFFFE`（backpack）不重疊。

## 4. 用字：全部重用已上線字形，沒有新增任何字模

`防`（794）／`禦`（560）／`靈`（822）／`能`（629）四字在專案主要 catalog
（`localization/cjk_mapping.json`）裡**已經是 `active: true`**，各有
6／1／48／59 次既有出現次數，代表它們已經在 ETen 對話字庫（bank 2／3）
中通過實機驗證。本版只是重用既有 ID，透過已驗證多次的 `ability_text`
三元組解碼流程產生 transport code，**沒有呼叫任何字形建置流程、沒有改動
任何字庫 bank**。

## 5. Bone 的現況（本輪未完成）

`Bone`（檔案 offset `0x4A109`）經由一個材質名稱指標表定位：
`0x40A80`～`0x40AAC` 是一串 4-byte 遠位址（`offset:segment`，全部落在
segment `0x4356`＝DGROUP），每項對應一種材質字串（`Bone`、及其他材質，
與 `re_72` 提到的 GERAKIS 裝備欄「Bone 長劍」「Wooden 棍棒」「Obsidian
武器」說明卡吻合）。已確認 `0x40A84` 這一項正確指回 `0x4A109`。

**尚未定位**：實際讀取這個表、把材質字串與武器基礎名稱組合起來的程式碼。
静態位元組搜尋（在整個 EXE 內找對 `0x40A80` 的立即值參照）本輪沒有找到
直接命中；下一步應該改用即時除錯（在 hover／右鍵說明卡觸發時對這個表的
記憶體位址下讀取斷點）而不是繼續盲猜靜態位址。`re_68` 沒有把 Bone
列為「已知技術阻礙」，很可能是因為材質字串最終會併入已證實可用的
NAME-slot 解碼路徑（與 hover／右鍵卡片共用），但這一輪沒有把這個假設
驗證到底。

## 6. 實作過程中的教訓（供下一版参考）

- **overlay relocation 檢查會抓到看似合理但實際危險的重新導向範圍**：
  PSI: 最初設計把可替換片段往後延伸到包含原始 `lcall 0x150:0x16D`
  本身，想省事直接在 FONT-local 程式碼裡重放整個遠呼叫；
  `verify_overlay_relocations` 立刻在建置期擋下（`0x6F628` 命中一個
  overlay relocation word），逼著改用往前擴充片段的方案。這證明
  `re_68`／`re_71` 一路強調的 overlay relocation 守門機制確實有效，
  遇到報錯時應該重新設計片段邊界，而不是想辦法繞過檢查。
- **Unicorn 16-bit 模擬測試抓到了純靜態分析看不出來的錯誤**：本輪新寫
  的 `ac_label_entry`／`psi_label_entry` 用 `si`／`di` 當暫存索引卻沒有
  `push`/`pop` 保護，組譯與連結都完全正常，直到用既有的
  `test_backpack_ui_candidate.BackpackMachineTests` 測試基底跑實際 16-bit
  執行才發現呼叫端的 `si`／`di` 被污染。任何新增的 FONT-local 進入點都
  應該補一組類似 `test_ability_ui_candidate.py`／`test_view_hover_candidate.py`
  的機器碼級測試，不能只靠組譯成功或位元組雜湊比對過關。
- **機器碼測試驗證的是「重新導向本身」的正確性，不是「跟呼叫端銜接」的
  正確性**：真正在 DOSBox-X 實機測試時，按物品欄快速鍵 `I` 會讓整個
  DOSBox-X 閃退。用二分法把 AC／PSI 兩個修補分開單獨套用（各自複製一份
  v60 EXE，只套一個 redirect）後確認：**AC 完全正常，PSI 單獨套用就會
  閃退**。追查後發現 `psi_decoded` 多推了三個字（
  `word ptr ds:[0x3270]`、`0x14`、`word ptr ds:[0x326e]`）——這三個字其實
  在被取代的片段**開始之前**就已經由原本、未被修改的程式碼推入堆疊了
  （見第 3 節：PSI 的可取代片段是往前擴充到 `0x6F60E` 才湊到 22 bytes
  下限，但這三個 push 仍停留在 `0x6F60E` 之前，屬於原始、未觸碰的程式
  碼）。`psi_decoded` 卻又把它們重推一次，導致堆疊多出 3 個字沒被
  `add sp,0x18` 收回，SP 持續偏移，最終腐化到把整個 DOSBox-X 弄崩潰。
  Unicorn 測試沒有抓到這個問題，因為測試的 harness 直接從 redirect stub
  開始執行，從沒有模擬「呼叫端在片段開始前已經推了什麼」，所以測試只驗證
  了 `psi_decoded` 自己push的內容彼此一致，驗證不到跟*真正*呼叫端的銜接
  錯誤。**教訓：修改片段邊界（尤其是往前/往後擴充）之後，必須重新核對
  「新納入片段內的每一個原始指令」都確實在重建邏輯裡覆蓋到，而「片段外
  的原始指令」一個都不能被重複模擬。**移除多餘的三個 push 後，11 項新
  測試與完整 144 項測試套件都仍然通過（因為原本測試就沒有涵蓋這個銜接
  面，必須修正後才补上正確的期望值）。

## 7. 驗證與限制

- 144 項單元／Unicorn 測試全部通過，無 skip（`pip install unicorn` 後
  確認），包含新增的 11 項 `tests/test_fixed_labels_candidate.py`。
- 建置腳本（`tools/build_fixed_labels_candidate.py`）的雜湊與 overlay
  relocation 檢查全部通過；EXE 只修改兩個既審查過的 14／37-byte 範圍，
  沒有新增 main-MZ relocation；RESOURCE 只有 FONT-100 改變，其餘 1204 個
  chunks 全部一致。
- **已完成 DOSBox-X 實機驗證**（使用者與 Claude 透過除錯器 MCP 共同操作）：
  載入存檔、按 `V` 進入 VIEW CHARACTER 確認能力值仍為中文；按 `I` 進入
  真正的物品欄，確認「靈能: 27/27」「防禦: 8」正確顯示、數字與冒號位置
  正常、六項能力值與「耐撞」「反制」武器傷害列不受影響，且**不再閃退**。
  發現與修正過程見第 6 節。
- VIEW CHARACTER 下半部（`Fighter/Druid/Psionic` 等多職業欄位）仍是原文，
  這在計畫內、非本版範圍。

重建與測試：

```powershell
python -m tools.build_fixed_labels_candidate --output scratch_test/cjk_display_staging_v61_fixed_labels
pip install unicorn
python -m unittest discover -s tests
```

## 8. 接續建議

1. **Bone**：改用即時除錯定位材質字串表（`0x40A80` 附近）的讀取程式碼，
   而不是繼續靜態猜測；確認它是否真的併入 NAME-slot 解碼路徑後才決定
   修補方式。
3. VIEW CHARACTER 下半部（性別／種族／陣營／職業）：既有 enum 查表發現
   代表下一步应该先靠即時除錯把 `0x538:0x2a`／`0x538:0x2f`／
   `0x580:0x84` 三個格式化進入點的實際字串來源（是否為固定字串表、
   是否可行經 NAME-slot）弄清楚，再決定要不要繼續走路線 A。
