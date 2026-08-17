# GPL local-sub 入口與鬥獸場囚犯對話

日期：2026-08-16

## 結論

鬥獸場內被綁囚犯的 `Talk` 無反應，已縮小為 **舊存檔與已重定位 trigger 的
相容性問題**，而不是文字翻譯本身。原版 GPL-5 以 `talktotrigger 0x092C, 5,
NAME(-280)` 建立囚犯；v23 正確重定位為 `0x093E`。該回呼會再以 GPL 的
`local sub` 進入囚犯對話（原 `0x065E`，v23 `0x0665`），所有 GPL 內部呼叫
也已同步重定位。

v22 建立的實體可能已把舊 trigger 狀態保存；把同一份存檔交給 v15 時，v15
仍在 `0x092C` 保有原始回呼，所以可正常開啟「水……給我一點」對話。v23 則在
`0x093E` 才有該回呼。這個假說可直接以**全新流程建立的 v23 存檔**驗證。
現有 SAV 檔未出現可安全識別的裸 `2C 09 05`／`3E 09 05` 值，故不能以猜測的
二進位取代方式遷移。

## 實測入口差異

`gpl-disasm --entries` 對原版與 v23 的結果如下。`0x0000`、`0x0001` 是共同
起點；其餘值是由 GPL 的 `local sub` 呼叫發現的函式入口。它們是有用的版面
診斷資訊，**不是**已證實的引擎外部入口表。

| chunk | 原版外部入口（除共同起點） | v23 對應入口 |
| --- | --- | --- |
| GPL-2 | `0156 0192 02BD 036F 040E 0B61 0BC3 0D96 0E05 104F 130B 13BC 158D 18B0 219E 2455 2525` | `014B 0187 02AD 035F 03FE 0B4D 0BAF 0D76 0DE2 1016 12E3 138D 1557 187A 2168 241F 24EF` |
| GPL-3 | `07C0` | `07C0`（v21/v22 出口 ABI 修復仍保留） |
| GPL-4 | `0F47 10DC 113C 131D` | `0F35 10E0 114C 1323` |
| GPL-5 | `0124 0474 0564 065E 0705 096D 0E78 0ED5 1854` | `0129 047D 056B 0665 071B 097F 0E53 0EA4 1819` |

這些偏移會隨可變長度文字移動；編譯器會重定位其 GPL 內部 `local sub` 呼叫。
因此單看這張表不能解釋囚犯失效，也不能要求所有函式入口固定不動。

## 已修正、但不是本問題根因的項目

v23 已將 GPL-5 兩個同 chunk 的 template trigger 目標隨字串重排：

- `talktotrigger`：`0x092C -> 0x093E`
- 另一個同 chunk trigger：`0x1982 -> 0x195D`

這些目標現在落在有效指令邊界，但不會改變引擎從外部直接跳到 `0x065E` 的行為。
因此不能把 trigger 重定位誤認為完整修復。

## 診斷用入口守門條件

`tools/compile_gpl_dialogue_patch.py` 新增的
`--preserve-external-entries` 會從原始 GPL 的 `gpl-disasm --entries` 取得所有
已發現的 local-sub 入口，並在組譯後驗證：

1. 原位址的首位元組 opcode 不變；
2. 原位址仍是反組譯後的**指令邊界**，而非剛好相同的資料或指令內部位元組。

以完整開場翻譯清單進行探測時，建置在第一個位移即停止：

```text
GPL-2: fixed external entry 0x0156 must start with 0x18, found 0x02
```

探測輸出目錄未建立，沒有污染 staging。這個選項可防止「有未重定位呼叫者」的
假設被忽略，但目前不可把它當成正式建置的必要條件，因為正常的 GPL 內部重定位
本就會移動這些函式。

## 下一步

不要再以單一舊位址直接覆寫存檔。

### v23 全新流程實測（2026-08-16）

已用全新流程到達鬥獸場，兩名被綁囚犯均能顯示目標 GUI 與 `TALK`，但按下後都
沒有對話。這排除了「僅舊 v22 存檔攜帶 stale trigger」的假設。

bridge RAM 掃描曾在實體 `0x72F15` 找到 v23 GPL-5：三個註冊指令分別保有
`09 3E 00 05`（兩筆）與 `19 5D 00 05`（一筆），不存在舊 `09 2C 00 05`。

曾對 GPL-5 `0x093E`／`0x195D` 設 DOSBox **x86 程式碼** breakpoint 而未命中；
此結果沒有診斷價值，因為這兩個數值是 GPL 解譯器讀取的資料偏移，不是 CPU 可執行
位址。所有該輪 breakpoint 已清除，且不得以「未命中」推論 callback 未執行。

下一步應以英文／v15 對照版成功點 Talk 時的實際 x86 `GplTalkCheck`／GPL interpreter
路徑為基準，再比較 v23 傳入的 `(chunk, offset, name)` 參數。不能再把 local-sub
清單或 GPL bytecode 位址誤當成引擎外部入口或 DOS code breakpoint 位址。

### v15 runtime trigger 表定位（2026-08-16）

在 v15 成功開啟囚犯對話時，取得 1 MiB RAM 快照；關閉對話後再取得第二份。雖然
UI／動畫造成 145,658 個變動 byte，實際 trigger 記錄在兩份快照都不變，位於實體
`0x71E23` 起的 12-byte records：

```text
0x71E23: 13 00  2C 09  05 00  E8 FE  00 00 00 00
                    ^target  ^GPL-5 ^NAME(-280)

0x71E2F: FF FF  82 19  05 00  C1 FE  00 00 00 00
                    ^target  ^GPL-5 ^NAME(-319)
```

第一筆精確對應囚犯一的原始 `talktotrigger 0x092C, 5, NAME(-280)`；第二筆精確
對應囚犯二的原始 `0x1982, 5, NAME(-319)`。因此這是可直接比較 v23 註冊結果的
runtime trigger 表，不需要再對 GPL bytecode 資料設定不會命中的 CPU breakpoint。

下一個 v23 實測應在囚犯 GUI 出現、尚未按 Talk 時掃描這種 records：預期兩筆
target 分別為 `0x093E` 與 `0x195D`。若仍是舊值或記錄不存在，即可將問題鎖定在
註冊；若新值正確，才繼續追 Talk dispatcher 的取用邏輯。

### v23 trigger 表比對與暫時覆寫反證（2026-08-16）

v23 到達囚犯旁、尚未按 Talk 時，同一張 runtime 表仍保有 v15 的舊值：

```text
NAME(-280): target 0x092C, GPL-5
NAME(-319): target 0x1982, GPL-5
```

這證實 GPL 位元碼內已重定位的 `talktotrigger` literal 沒有反映到這張 runtime
表。然而以 bridge **僅在 RAM** 暫時將兩筆 target 改成 `0x093E`／`0x195D` 後，
兩名囚犯仍無反應。測試結束後以 read-back 指紋驗證並還原為原始舊值；未改寫 SAV
或任何遊戲檔。

因此 trigger 表是有關聯的模板／索引，但不是 Talk dispatcher 最終使用的唯一狀態。
後續必須追查它建立後衍生的物件快取或 callback pointer；不得把這張表的兩個 word
直接當成正式修復點。

在尚未完成前：

- v15 仍是正式可玩 checkpoint；
- v22 保留為已驗證出口修復的實驗 staging；
- v23 保留為已修正 template-trigger 重定位、等待全新存檔驗證的 staging，
  **不可**升格。

## GPLI-1 事件位址表：根因與 v25 修復（2026-08-16）

先前的「runtime 表仍是舊位址」不是存檔直接保存裸 GPL offset；它由
`GPLDATA.GFF/GPLI-1` 的固定 6-byte record 表產生：

```text
event_id:u16le, gpl_offset:u16le, gpl_chunk:u16le
```

原版／v23 的兩筆囚犯項位於 GPLI-1 相對偏移 `0x0984`／`0x09BA`：

```text
18 00  2C 09  05 00    # event 0x18 -> GPL-5@0x092C
1A 00  82 19  05 00    # event 0x1A -> GPL-5@0x1982
```

它們正是 `SAVE-37` 中囚犯事件索引 `0x18`／`0x1A` 於讀檔後所展開的舊 runtime
target。`RGN05.GFF/ETAB-5` 也含 event `0x18` 的三個 8-byte 實體記錄，因而把問題
可靠地連到競技場區域資料，而不必猜測 GMAP/RMAP 的欄位。

DOSBox-X-AI real-mode write watchpoint 兩次命中提供了動態證據：第一次停在 DOS
`INT 21h/AH=3F` 讀入 `DARKRUN.GFF/SAVE-37`；第二次停在遊戲碼
`5B7C:1D04..1D68`。該迴圈以 6-byte GPLI 來源項的 `(event_id, offset, chunk)`
比對事件索引，並把 offset 寫入 13-byte runtime trigger record。囚犯一命中時
來源記憶體為 `18 00 2C 09 05 00`，且 `AX=0x092C`。

`tools/compile_gpl_dialogue_patch.py` 現新增保守的 GPLI relocation：只要第三欄指向
本次已重組的 GPL chunk，且第二欄是原始 GPL 指令邊界，便以該 chunk 的 offset map
更新；其餘 GPLI 項保持不變。合成單元測試覆蓋已知邊界、未知 offset、其他 chunk。

由此產生：

```text
scratch_test/gpl5_gpli_relocation_v1
scratch_test/cjk_display_staging_v25_gpli_event_relocation
```

v25 的 GPLI-1 已正確包含：

```text
18 00  3E 09  05 00    # event 0x18 -> GPL-5@0x093E
1A 00  5D 19  05 00    # event 0x1A -> GPL-5@0x195D
```

實機載入既有 `SAVE05` 後，兩名被綁囚犯皆已成功開啟對話（含第一句繁中內容）；
因此此修復不依賴重跑流程或遷移存檔。v25 尚需出口 Yes/No 與戰鬥的最小回歸後，
才評估是否升格為新的正式 checkpoint。
