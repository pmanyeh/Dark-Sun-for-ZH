# v68 職業名稱：純資料表 patch 失敗，找到真正原因

日期：2026-09-17

延續 `re_89`。原本以為職業名稱表（`DS:0x1200` 指標表 ＋ `DS:0x128D`
英文字串池）是純資料，直接改成中文 tag-encoded 位元組就能用，不需要
像陣營/性別那樣另外寫 FONT-local 解碼＋tag redirect。**這個假設實機
測試後證實是錯的**，記錄下來避免下次重蹈覆轍。

## 1. 結論

`scratch_test/cjk_display_staging_v68_view_class_names` 建置腳本本身
的一致性檢查全部通過（位元組核對、relocation 防護、GFF 校驗），但
**實機測試失敗**：GERAKIS 原本顯示「Gladiator」的位置變成亂碼。這個
候選版**不能用**，已停用，不建議繼續往下修，應該按照第3節的正確做法
重新設計。

## 2. 為什麼直接改資料不行

用中斷點確認：實機讀出來的表格內容完全正確（`鬥士`的 Base94 tag
bytes `5E 2A 2C 5E 2B 61 00` 逐位元組吻合預期），問題不在資料，
而在**這個呼叫路徑完全沒有經過 CJK 解碼管線**。

之前每一個成功的欄位（性別／種族／陣營／HP:／PSI:）都是靠**tag
redirect**把 `ax` 設成一個特定數值、跳進 FONT 端的
`cjk_name_cache_start`，由它的 `decode_start` 迴圈把 `0x5E` 開頭的
三聯組**轉換成「使用哪個已載入字形 slot」的 transport code**，再把
轉換後的 transport code 緩衝區位址交給共用繪字函式
`339E:016D`。`0x5E` 三聯組本身**不是** `339E:016D` 認得的格式——它
只認得 transport code；`0x5E`／三聯組的意義完全是 `decode_start`
自己定義的私有格式。

職業名稱的呼叫路徑（`5B7C:2F1F`＝單職、`5B7C:2E56`起＝三職，兩者都
確認過）是**直接**：

```text
les  bx,[bp+0A]          ; 角色紀錄
mov  al,es:[bx+21]       ; 職業ID（1-indexed）
cbw
dec  ax
shl  ax,02
mov  bx,ax
push dword [bx+si]       ; si=0x1200，直接把「表格裡存的遠指標」當字串位址
...
call 339E:016D           ; 直接把上面那個字串位址交給繪字函式
```

中間完全沒有經過 `decode_start`。所以只要表格／字串池裡放的是
`0x5E` 三聯組，`339E:016D` 就會把它們當成一般 ASCII／`%C` 控制碼
逐位元組印出來，變成亂碼——這不是資料錯誤，是**這個呼叫路徑的設計
本來就只支援純 ASCII**，跟性別/種族/陣營的機制完全不同種類。

## 3. 正確做法：比照 HP:/PSI:，但要處理多個呼叫點

職業繪圖函式（`5B7C:2DC1`，overlay 48／`5B7C` 這次即時載入的
segment）依「目前有幾個職業」分成三條路徑，**各自獨立**做
「讀職業ID→查表→push指標」，所以同一個「職業欄位1」的讀取／push
邏輯，其實在原始碼裡**出現了三次**（單職路徑一次、雙職路徑一次、
三職路徑一次），職業欄位2 出現兩次（雙職、三職路徑），職業欄位3
只出現一次（三職路徑）——**總共 6 個實體 patch 點**，不是 1 個。

每個 patch 點都要比照 `re_89` 的 `ds_relative_consumer_redirect_bytes`
手法（因為都在同一個易變 overlay 裡）：換算「patch 點結束位置」相對
overlay file_start（`0x89E70`）的 local IP，設 `mov ax,<tag>` ＋
14-byte DS-relative redirect，跳進一個**新的 FONT-local 職業名稱
解碼器**（讀 `[bp+0A]` 記錄、讀對應職業欄位、比照 `race_offsets`
的「可變長度＋offset table」風格查一份新的中文職業名稱表、把結果
交給 `decode_start`，最後把 transport code 指標交還呼叫端）。三個
欄位（1/2/3）可以共用 3 個 FONT-side 解碼器（欄位1一個、欄位2一個、
欄位3一個），但 EXE 端仍然要在 6 個不同位置分別下 redirect（因為
每個路徑裡的呼叫點是不同的實體位元組位置，continuation IP 各自不同）。

另外還沒驗證：量寬 helper（`call 2F59`，決定「/」分隔線在哪裡）
量的是「字串位元組數」還是「解碼後的視覺寬度」——如果是前者，多職
情況下的「/」位置很可能因為中文 tag 字串位元組數（每字3 bytes）遠
大於視覺寬度而跑位，需要一併處理或至少驗證。

## 4. 建議

這比原先估計的工程量大很多（6 個 patch 點 + 新職業名稱表 + 量寬
helper 相容性待驗證），性質上跟「陣營」那次差不多重（甚至更多
patch 點）。建議另開一輪專門處理，先把單一職業（1-class 路徑，只有
1 個 patch 點）做出來驗證整條「FONT 解碼器→transport code→
339E:016D」管線可行，再擴充到 2/3 職路徑。

## 5. 已知安全，未受影響

沒有動到任何已驗證過的 EXE／FONT 內容；`v68` 目錄可以直接刪除或
留著當反面教材，不影響 `v67`（HP:/PSI: 標籤）以前的所有進度。
