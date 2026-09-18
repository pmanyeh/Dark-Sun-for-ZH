# v67：VIEW CHARACTER 的 HP:／PSI: 標籤中文化（已實機驗證）

日期：2026-09-17

延續 `re_88` 第 6.5 節留下的問題：VIEW CHARACTER 自己的 `HP:`／`PSI:`
標籤，推字串位址的組合語言住在一個會被 DOS overlay manager 動態換頁的
overlay 單元裡，不能像性別／種族／陣營那樣直接假設「這次看到的 segment
永遠不變」。這次找到正確做法並完成實機驗證。

## 1. 結論

`scratch_test/cjk_display_staging_v67_view_hp_psi_labels` 已實機驗證：
GERAKIS 畫面正確顯示「生命: 54/54」「靈能: 27/27」，陣營／性別／種族／
防禦／DAM 均不受影響。

## 2. 關鍵線索：另一個獨立專案已經證實過同一個 overlay

使用者提示去查 `d:\git\dsun-hires-text-poc`（一個獨立、範圍窄很多的
「高解析度文字」實驗專案）。它的交接文件直接寫著：

> Hover移植來自原專案已驗收v60：EXE `0x8A925..0x8A933`，**overlay48起點
> `0x89E70`**，continuation IP `0x0AC3`；**14-byte DS-relative redirect
> 不新增relocation**。

這跟本專案自己在 `re_88` 用 `vendor/opends/tools/ovr-map/ovr-map.py`
查到的 overlay 表格（`index=0x30`／十進位48、`file_start=0x89E70`）完全
對上，而且**本專案自己也早就有這個已驗收的先例**——`tools/
build_view_hover_candidate.py`（`v60`，裝備格 hover 名稱解碼）：

```python
HOVER_SITE = 0x8A925
HOVER_CONTINUATION_IP = 0x0AC3   # 0x8A925 + 14 - 0x89E70
replacement = ds_relative_consumer_redirect_bytes(HOVER_CONTINUATION_IP)
```

`ds_relative_consumer_redirect_bytes`（`tools/plan_name_slot_consumers.py`）
產生的 14 bytes 是 `push cs; push <continuation_ip>; mov bx,ds; sub
bh,0x10; push bx; push 0x0714; retf`——**`push cs` 當場捕捉「這次真正
跑在哪個 segment」**，只需要一個「相對 overlay 自己開頭的固定位移」
（`continuation_ip = 檔案位移 - overlay file_start`），完全不必假設
「這次剛好在 5EBF」會一直成立。之前 `re_88` 卡住，是因為誤以為要重現
`self_relative_tag_redirect` 那種需要 22 bytes 的自我計算位址手法，
沒注意到已經有這個更輕量、專為 overlay 內容設計的 14-byte 版本，而且
本專案自己就已經驗證過。

## 3. Patch 位置與做法

`HP:`（`"%C%C%CHP:\0"`）與 `PSI:`（`"%C%C%CPSI:\0"`）兩段字串本身位於
常駐 `DS` 段（分別在 `DS:0x3363`／`DS:0x336D`，內容用中斷點＋記憶體讀取
確認過跟畫面吻合），但**推這兩個位址的組合語言**在 overlay 48 內：

```text
push word ptr ds:[0x3270]     ; 顏色（不用動）
push 0x14                     ; 版面模板 id（不用動）
push word ptr ds:[0x326E]     ; 顏色（不用動，其運算元字組也是 relocation）
push dword 0x00FE00FF         ; 顏色 escape（要重推）
push 0                        ; （要重推）
push ds; push 0x3363/0x336D   ; 字串遠指標 ← 唯一要換的東西
push dword <Y,X>              ; 位置（要重推，值固定不變）
push dword [bp+?]             ; 呼叫端遠指標（不用動）
call <relocation-protected>   ; far call，segment word 絕不能碰
```

只把「`push dword 0x00FE00FF; push 0; push ds; push 字串位移;
push dword Y,X`」這 18 bytes（HP 位於檔案位移 `0x8A2AA`，PSI 位於
`0x8A320`）換成：3 bytes `mov ax,外層tag` ＋ 14 bytes 的
`ds_relative_consumer_redirect_bytes`，跳到 FONT 端的
`view_hp_decoded`／`view_psi_decoded`，兩者各自重推同樣的顏色／位置
參數，只把字串指標換成 `cs:view_hp_buffer`／`cs:view_psi_buffer`，再
`retf` 回到 overlay 自己「已跳過」的那一段（緊接著的 far call，原封
不動）。前面的 `push word[3270]`／`0x14`／`push word[326E]` 完全不去
動，後面 far call 的 relocation segment word 也完全不去動——兩處都是
`verify_overlay_relocations` 卡過的地方（分別在 `push word[326E]` 的
運算元、以及 far call 前一個 `mov ax,SEGMENT_PLACEHOLDER` 的立即值），
親自試過才確認邊界。

`tools/cjk_name_slot_cache.asm` 新增 `view_hp_label_entry`／
`view_hp_decoded`（外層 tag `0xFFC9`，內層 tag `0xFFF8`）與
`view_psi_label_entry`／`view_psi_decoded`（外層 `0xFFCA`，內層
`0xFFF9`），機制比照 `re_83` 已驗證的 `psi_label_entry`（用
`ability_text` 巨集＋既有 `label_sources` 解碼管線，只是這次
`label_sources` 從 2 筆擴充成 4 筆，`assemble_name_slot_cache` 的
`label_ids` 參數跟著從 4 個 id 擴充成 8 個）。「生命」（生507／命139）
「靈能」（822／629，跟 `re_83` 的 PSI 譯名一致）都是已上線字形，
沒有新增字模。

## 4. 尚未完成

- 等級／職業／經驗值／HP·PSI 數字／AC·DAM 數字仍是英文，見 `re_88`。
  下一步查這些欄位的呼叫點時，同樣要先用 `ovr-map.py` 確認是否落在某個
  overlay 裡、correlation IP 怎麼算，不能只憑一次即時反組譯記錄的
  segment 位址。

## 5. Hashes

```text
v67 DSUN.EXE
39a18dd6e6c9c80e9a3076929cece2bdc4453c1b5950471ee2ffba7b9e4d101b
v67 RESOURCE.GFF
3520b38388cd60cf3f379a41df4707ab899989c344fc51ff21a60610b5a4f589
```

建置腳本：`tools/build_view_hp_psi_labels_candidate.py`（parent 為 v66b,
`scratch_test/cjk_display_staging_v66b_view_alignment_reposition`）。
