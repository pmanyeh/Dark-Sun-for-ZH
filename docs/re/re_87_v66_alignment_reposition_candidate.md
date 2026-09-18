# v66：陣營搬到裝備格那排、性別歸位跟種族合併

日期：2026-09-17

延續 `re_85`／`re_86`。使用者提供新排版示意圖：「陣營」搬到裝備格那一排（性別原本
v65 待的位置），「性別」搬回種族那一行（跟 v64 一樣，兩者合併同一行）。這次同步
找到陣營真正的繪製位置並完成中文化。

## 1. 結論

`scratch_test/cjk_display_staging_v66b_view_alignment_reposition` 已實機驗證：
陣營（例如 GERAKIS 的「混亂善良」）正確顯示在裝備格那一排，性別／種族維持 v64
原樣合併在同一行。第一版（`..._v66_...`，未加 `b`）建置腳本內建的一致性檢查雖然
全部通過，但使用者實機測試時性別／種族那一行顯示成亂碼——這是本次修改自己的
bug（見第 4 節），已在 `..._v66b_...` 修正並重新確認正常。

v66 是接在 **v64** 之後（不是 v65）：v64 的性別＋種族本來就已經合併在同一行，
v65 把性別搬去裝備格那排是上一版走的方向，這次改成陣營搬過去，所以直接跳過
v65 那個中間態，性別／種族維持 v64 原樣即可。

## 2. 陣營繪製位置：re_86 的死路走岔在哪裡

用跟 v64/v65 找性別／種族一樣的「設中斷點＋單步執行」，這次直接用非人類角色
（GERAKIS＝半巨人）重新驗證 `5FB0:19A8`（file offset `0x64BF8`，即 re_72 舊記錄
`0x8A1DC` 呼叫點的真正跳轉目標）：

```text
19A8: push bp
19A9: mov  bp,sp
19AB: les  bx,[bp+0A]        ; ES:BX = 角色身分紀錄指標
19AE: mov  al,es:[bx+1A]     ; AL = record+0x1A ← 陣營！
19B2: cbw
19B3: shl  ax,02             ; ×4，索引一張「遠指標表」
19B6: mov  bx,ax
19B8: push dword [bx+0F06]   ; push 陣營英文字串的遠指標
19BD: push word [3270]
19C1: push 0014
19C3: push word [326E]
19C7: push 00FE00FF          ; 顏色跳脫碼
19CD: push 0000
19CF: push ds
19D0: push 0E11              ; 版面模板 id
19D3: push word [bp+10]      ; Y（原本 93）
19D6: push word [bp+0E]      ; X（原本 149）
19D9: push dword [bp+06]     ; 呼叫端自己的遠指標參數，原樣轉發
19DD: call 339E:016D         ; 跟性別／種族／AC:／PSI: 共用的同一個格式化函式
```

實機讀出 GERAKIS 的 `record+0x1A = 0x07`，經過表格查到的字串是 `"CHAOTIC GOOD\0"`；
K'RATCHEK 的 `record+0x1A = 0x05` 對應 `"TRUE NEUTRAL"`——兩者都跟畫面上顯示的
陣營完全吻合。**`5FB0:19A8` 就是陣營的真正繪製函式，而且它的收尾參數順序
（顏色跳脫碼、版面模板 id、位置、呼叫端遠指標）跟性別的繪製呼叫一模一樣。**

`re_86` 判定「這是無關邏輯（人類種族＋職業等級≥2 的彈出訊息檢查）」的結論是
誤判：那段「檢查 `es:[bx+0x18]==1`」的程式碼，其實是**下一個欄位**
（`5FB0:19E7` 起）的內容，在 `5FB0:19A8` 自己的 `retf`（`19E6`）之後才開始。
`re_86` 追蹤時應該是看過了 `retf` 分界，把下一段誤認成同一段的延續。

### 2.1 陣營欄位編碼

`record+0x1A`，1-indexed 1–9，順序照 AD&D 經典 3×3 表格「先守序/中立/混亂、
再列善良/中立/邪惡」橫向排列：

| 值 | 英文 | 中文 |
|---|---|---|
| 1 | LAWFUL GOOD | 守序善良 |
| 2 | LAWFUL NEUTRAL | 守序中立 |
| 3 | LAWFUL EVIL | 守序邪惡 |
| 4 | NEUTRAL GOOD | 中立善良 |
| 5 | TRUE NEUTRAL | 絕對中立 |
| 6 | NEUTRAL EVIL | 中立邪惡 |
| 7 | CHAOTIC GOOD | 混亂善良 |
| 8 | CHAOTIC NEUTRAL | 混亂中立 |
| 9 | CHAOTIC EVIL | 混亂邪惡 |

這個欄位緊接在種族（`+0x18`）、性別（`+0x19`）之後，跟 `vendor/opends`
`save-inspect.py` 記載的 DS1 存檔格式 `ds_character_t`（`race`／`gender`／
`alignment` 三個欄位依序相鄰）完全對得上，兩者共用同一份原始欄位配置。

## 3. Patch 方式

陣營跟性別的呼叫參數結構幾乎一模一樣，因此直接比照 v65 `gender_decoded` 的
做法：一段 50-byte 的 tag redirect，從 `les bx,[bp+0xA]` 一路吸收到（但不含）
`call 0150:016D`（segment word 是 overlay relocation 目標，永遠不能覆寫）這個
far call 本身，換成新的 FONT-local `alignment_decoded`：自己重新讀
`record+0x1A`、查一張新的九筆中文字串表、把原本的 `push [bp+10]／[bp+0E]`
（Y／X）換成寫死的 `ALIGNMENT_Y=44, ALIGNMENT_X=149`，其餘顏色／模板／呼叫端
參數原樣重新 push 一次，最後掉到未動過的 far call 上。

- `ALIGNMENT_SITE = 0x64BFB`，長度 50 bytes，外層 tag `0xFFCB`，內層範圍
  `0xFFC0-0xFFC8`（9 筆，固定 16-byte stride，因為 9 種陣營譯名都剛好是
  4 個字）。
- 性別／種族完全比照 v64：`gender_decoded` 改回 v64 原本的短版 tag redirect
  （跟 `race_decoded`同形狀，只重建字串指標，不覆寫位置），種族程式碼完全沒動。
- `tools/cjk_name_slot_cache.asm` 新增 `ALIGNMENT_Y`／`ALIGNMENT_X` 常數、
  外層／內層 tag 分派、`alignment_text` 巨集（比 `identity_text` 多兩組
  Base94 三聯組）、`alignment_sources` 資料表、`alignment_label_entry`／
  `alignment_decoded`。`tools/plan_name_slot_consumers.py` 的
  `assemble_name_slot_cache()` 新增 `alignment_position` 參數。

### 3.1 新字形

陣營译名共 12 個不同字：守序善良中立絕對邪惡混亂。其中「序、善、良、立」
4 個在既有 `cjk-mapping-v57.json`（v64 那份複本）裡沒有，新增後全部落在
bank 5（跟 v64 新增穆／螂／螳同一個 bank），bank 5 從 40 個字擴充到 44 個，
沿用同一套 `Fusion_Pixel_10px.ttf` 光柵化參數，bank 0–4 逐位元組不變。

## 4. 第一版的 bug：FONT 跟 EXE 版本對不起來

第一次建置（純用建置腳本自己的一致性檢查全部通過）給使用者實機測試後，
GERAKIS 的畫面顯示陣營「混亂善良」正確，但性別／種族那一行變成亂碼
（例如 `syNF半▯,FU,0wF費F3uFtFNaN`，只有「半」一個字正確）。

根因：`tools/cjk_name_slot_cache.asm` 裡的 `gender_decoded` 當時還是 **v65**
留下的版本——v65 為了把性別搬去裝備格那排，把原本 22 bytes 的 tag redirect
擴大成 46 bytes，讓 FONT 端自己額外重新 push 顏色跳脫碼／版面模板／位置／
呼叫端遠指標等一整串參數。但 v66 是接在 **v64** 的 EXE 上，v64 那份 EXE 裡
`GENDER_ZONE_C` 依然是原本 22 bytes 的短版（只換字串指標，其餘參數留給
EXE 自己原本沒動過的程式碼繼續 push）。FONT 端（v65 的長版）跟 EXE 端
（v64 的短版）兩邊都各自 push 了一份顏色／位置／遠指標參數，多出來的堆疊
內容讓 `add sp,0x1c` 清不乾淨，把同一個共用堆疊框架裡緊接著要畫的種族
一起帶壞。

修正方式：把 `gender_decoded` 改回跟 `race_decoded` 一樣的短版（只重建
`dx:ax` 字串指標＋重新 push `word ptr ds:[0x3270]`，其餘全部交回 EXE 原本
未動過的程式碼），不再需要 `GENDER_Y`／`GENDER_X`。修正後的建置目錄是
`scratch_test/cjk_display_staging_v66b_view_alignment_reposition`，使用者
實機測試 GERAKIS 確認陣營／性別／種族都正常顯示。

這次教訓：`tools/cjk_name_slot_cache.asm` 是「每個候選版直接編輯共用原始碼」
的慣例，換 parent EXE（例如從 v65 系列切回 v64）時，必須連帶檢查共用原始碼
裡有沒有殘留「只為了配合另一個 parent 版本」而改動、尚未跟新 parent 對齊的
函式，不能只看新加的那塊程式碼有沒有問題。

## 5. 尚未完成／已知限制

- 職業／等級／經驗／HP／PSI 完全還沒開始（跟 re_86 一樣）。
- 「絕對中立」是這次選用的 True Neutral 譯名（4 字，跟其餘 8 種陣營一致寬度）；
  如果使用者有偏好的既有譯名（例如「純粹中立」），下次可以直接改
  `tools/cjk_name_slot_cache.asm` 裡 `alignment_sources` 對應那一行的
  Base94 參數重新 rebuild，不需要動 EXE patch。

## 6. Hashes

第一版（有 bug，僅供對照，不要部署）：

```text
v66 DSUN.EXE
dc4e44ce9019b1bba4ecb0c192ba44302ebd4fadeb7366f982ee5a3e6e57d32d
v66 RESOURCE.GFF
92e23a5fbee7d41501ef62d545e1fd801ab13ea8829158c10cd92504d51a83b3
```

修正後、已實機驗證的 v66b：

```text
v66b DSUN.EXE（跟第一版相同，只有 FONT 內容變了）
dc4e44ce9019b1bba4ecb0c192ba44302ebd4fadeb7366f982ee5a3e6e57d32d
v66b RESOURCE.GFF
2122791e2494fa2f96b128a0ddf9dfd175e752e710bbf6874d8261b3dedefc0a
v66b C5（新字形 bank，40→44 個字，跟第一版相同）
6ba75f11ce4085d47443c2846719823bcaa8e3faa8f104514691c3955bb95ea6
```

建置腳本：`tools/build_view_alignment_reposition_candidate.py`（parent 為 v64,
`scratch_test/cjk_display_staging_v64_view_identity`）。
