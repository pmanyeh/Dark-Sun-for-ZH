# 逃獄出口無反應：外部 GPL entry point 與區域格式縮小

## 2026-08-16：v15/v20 同流程旗標實測與出口 ABI 結論

以具 real-mode memory watchpoint 的 DOSBox-X bridge，從戰鬥前存檔完整走過
「放出獸群 → 第一戰結束 → 回嗆司儀」；兩版的 `SAVE-29` runtime copy 都位於
`7000:2744`。在回嗆司儀的同一選項後，v15 與 v20 都執行相同的持久狀態寫入：

```text
SAVE-29[1]: 0x12 -> 0x1A   (whole prefix: 00 12 01 -> 00 1A 01)
ECX:        000C000B
EAX:        08
writer:     0C61:2B47  or es:[bx], al
```

之後 v20 仍在同一出口無反應。因此「戰鬥勝利／回嗆司儀所需的劇情旗標未寫入」已被
實機排除；`GMAP`、`RMAP`、`ETAB` 之外也沒有其他 RGN02 chunk（僅這四類加 TILE）。

同時，實際 bytecode 已證實：v15 的外部出口 ABI 在 `GPL-3@0x07C0` 以
`0x2A` (`clearpic`) 開始；v20 的 `0x07C0` 是 `0x00`，正確腳本起點改為
`GPL-3@0x07D6` 的 `0x2A`。後續 v21 將此 entry 精確恢復為 `0x07C0`，而不改任何
地圖／旗標資料，出口對話與 Yes 後轉場均恢復正常；故未重定位的外部 entry callback
已由實機反證確立為直接根因。

不要直接覆寫 v20 `0x07C0` 做跳板：它位於前一個 `tport` 指令的參數中。修復須以
重組後維持 `0x07C0` ABI 的方式進行，而不是破壞前段流程。

## 2026-08-16：v21 固定 entry ABI 修補實機通過

以 `scratch_test/gpl_opening_arc_v4_global_sub_fix/GPLDATA.GFF` 為基底，只重組 GPL-3
中 entry 前的兩句競技場旁白，使 chunk 從 v20 的 2329 bytes 回到 2307 bytes；因此
外部出口 entry 回到原 ABI 位址 `0x07C0`，首 byte 為 `0x2A` (`clearpic`)。候選封包與
可玩 staging 分別為：

- `scratch_test/gpl3_exit_entry_abi_v1`
- `scratch_test/cjk_display_staging_v21_exit_abi_fix`

實機在可離開的競技場出口點擊後，成功出現繁中「這條走廊通往下方的奴隸欄。你要繼續嗎？」
確認；選 Yes 後亦成功轉場到守衛庫爾扎克的後續對話。這同時排除 GMAP/RMAP/ETAB、
gflag 寫入和地圖通行判斷為該缺陷的直接原因。

`tools/compile_gpl_dialogue_patch.py` 現已支援
`--require-fixed-entry GPL:3:0x07C0:0x2A`：任何日後重組若讓此 ABI 位址不是 `clearpic`
開頭，建置會直接失敗。`tools/build_cjk_display_staging.py` 亦會讀取封包的
`abi_constraint`，從最終 GPLDATA 再抽取 GPL-3 驗證該 byte。v22
`scratch_test/cjk_display_staging_v22_exit_abi_guard_rebuild` 已從 v21 候選封包重建，
GPLDATA SHA-256 與 v21 完全相同，並記錄 `verified_chunk_bytes: 2307`。對應單元測試、
v21 chunk 守衛與 v22 staging 守衛均已通過。

## 2026-08-16：v15 出口鎖定／解鎖對照更正

先前將 v15 的 `SAVE03.SAV` → `SAVE04.SAV` 誤稱為 GPL-4「衝向西側出口」
選項前後，這是不正確的。

- `SAVE03.SAV`：競技場戰鬥前；出口必須無反應，因為尚不可離開。
- `SAVE04.SAV`：戰鬥勝利、被叫回去休息後；點擊同一出口會出現離開確認。

因此這組存檔是同版本、同區域、同出口的「鎖定 → 解鎖」有效對照，應優先用來
找出出口判斷路徑及其狀態資料。它不單獨證明任何 `SAVE-*` chunk 或位元就是
`gflag22`；先前把 `SAVE-29` 視為 gflag22 候選的說法撤回，僅保留其為小型狀態
位元集合的觀察。

> 日期：2026-08-16  
> 延續：`re_42_opening_arc_dialogue_batch_and_gpl_branch_relocation_gaps.md`
> 狀態：v21 已修復並通過出口／轉場實機驗證；尚未升格正式 checkpoint。

## 結論摘要

v15 與 v20 的 33 個 `RGN*.GFF`（含所有 `GMAP`／`RMAP`／`ETAB`）逐檔 SHA-256
完全相同，`RESOURCE.GFF` 亦相同。故「翻譯匯入改壞某個區域檔」可排除。
`DSUN.EXE` 只有 30 個差異位元組，均限於 CJK bank 檔名表與 bank count（4→5），
不涉及地圖或旗標處理程式。兩版真正有語意差異的資料面是 `GPLDATA.GFF`。

OpenDS 的已驗證格式資料亦修正了先前過寬的假設：

- `RMAP`：`128 × 98 = 12,544` bytes，單位元組圖磚索引；
- `GMAP`：同大小，低 5 bits 為牆索引，高 3 bits 為通行／高度／互動旗標；
- `ETAB`：8-byte 記錄，僅含 `(x, y, y_offset, byte5, ojff_number)` 的實體放置資料。

因此這三個區域 chunk 本身沒有容納 `(gflag id, GPL chunk, GPL offset)` 的欄位；
「gflag22 直接由 GMAP/ETAB 查詢」不能再當作主要假設。出口條件若依賴旗標，應在
引擎／存檔狀態層依座標與區域旗標處理，而非直接編碼於這些格式中。

## GPL-3 出口 entry point 的位移

`gpl-disasm --entries` 顯示出口提示所在的 GPL-3 獨立 entry point 被翻譯前段內容推移：

```text
                 v15       v20
GPL-3 entry       0x07C0    0x07D6
提示 print string  0x07C1    0x07D7
```

此 entry 的原始內容正是：

```text
clearpic
"This corridor leads down to the slavepens."
"Do you wish to continue?"
getyn
```

它非常符合「走到出口時被外部系統呼叫」的行為。雖未直接捕捉該外部呼叫端，v21
僅恢復 `GPL-3@0x07C0` 的正確入口、未改變旗標或地圖資料，即同時恢復出口確認與
轉場；這個因果實驗已足以確認入口位移為直接根因。

已重新掃描全 GPL 的 `0x14 gpl global sub` 圖：沒有任何呼叫指向 GPL-3 的
`0x07C0` 或 `0x07C1`；僅有 GPL-2→GPL-3@68、GPL-154→GPL-3@374。因此呼叫端
若存在，不是可辨識的 GPL global-sub。

## gflag22 的實際範圍

GPL-4 的「衝向西側出口」分支在 v20 的 `0x1146` 正確執行：

```text
gpl load variable 1, gflag22
gpl local ret
```

同一個 chunk 對 `gflag22` 的其他讀取僅在 GPL-4 內部逃獄對話分支（v20
`0x0EB8`）出現。GPL-3 出口 entry 的提示／確認序列不讀取 `gflag22`。這表示
gflag22 是該對話流程狀態，而不是出口通行旗標；v21 的修補未改動它仍可正常離開，
故不能據此推論區域檔格式。

## 實機 v15/v20 出口比較（2026-08-16）

同一個 DOSBox-X-AI bridge 以唯讀暫停／記憶體掃描比較兩版的出口接觸結果：

| 情境 | 結果 | GPL-3 在 RAM |
|---|---|---|
| v15，踏入出口 | 顯示 `This corridor leads down to the slavepens...`／Yes-No 提示 | 已按需載入；chunk base `7000:2F14`，外部 entry `7000:36D4`（`+0x07C0`） |
| v20，踏入同一出口，無反應 | 無對話、無場景切換 | 掃描 1 MiB conventional memory，未找到 GPL-3 chunk 的前 64 bytes |

英文提示存在本身證實事件已派發到 GPL-3。v20 在事件結束後的 RAM 掃描未找到
GPL-3，表示它沒有留下常駐 cache；現在可合理解釋為 chunk 曾被短暫載入、以錯誤
entry 位址立即返回後釋放。v21 的最小 ABI 修補已將此推論驗證為正確，無須再追
loader／event dispatcher 才能判定直接根因。

兩次暫停時 CPU 都落在常駐 `37E6:03xx` callback；該位置不可單獨當作 GPL 已執行的
證據。後續實測亦已排除 `394F:000A` 作為事件入口：它只把 far pointer 轉成段位址；
`37E6:04DC` 是緊接著的資料複製例程。兩者都會被任何滑鼠命令共用，不能當作門口
條件 breakpoint。不要再使用這兩個地址推論門口事件；應先由存檔差分定位前置狀態，
或找到真正的地圖移動 dispatcher 後再設點。

## 已排除的誤命中

對全遊戲檔搜尋 bytes `C0 07 03` 曾在 `DSUN.EXE@0x8C133` 找到唯一命中；反組譯後
證實為 `6B C0 07`（`imul ax, ax, 7`）跨接的巧合序列，並非 GPL-3 entry 參照。
不要將它當作 trigger table 證據。

## 後續工作

出口缺陷本身已結案。後續只需將 v21 的固定 entry guard 納入正式封包建置，並在升格
checkpoint 前回歸確認競技場戰鬥、出口 No 返回與 Yes 轉場。
