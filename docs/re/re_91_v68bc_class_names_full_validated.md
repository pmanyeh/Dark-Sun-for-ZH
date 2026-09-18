# v68b/v68c：職業名稱（含多職業）中文化，已實機驗證全部四位角色

日期：2026-09-17

延續 `re_90`。上一版（v68）純資料表 patch 失敗後，改用跟性別/種族/
陣營/HP:/PSI: 一樣的「tag redirect → FONT 解碼器」正規做法，分兩步
（先驗證單職路徑，再擴充到雙職／三職路徑），GERAKIS／K'RATCHEK／
CERMAK／CILLA 四位角色全部實機驗證通過。

## 1. 結論

- **v68b**（`scratch_test/cjk_display_staging_v68b_view_class_names_slot1`）：
  只修單職路徑（`5B7C:2F1F`），實機確認 GERAKIS「Gladiator」→「角鬥士」
  正確顯示，K'RATCHEK／CERMAK／CILLA（雙職／三職）維持原文不受影響。
- **v68c**（`scratch_test/cjk_display_staging_v68c_view_class_names_full`）：
  補上雙職路徑（`5B7C:2EC9`）與三職路徑（`5B7C:2E56`）剩下的 5 個
  patch 點，實機確認：
  - GERAKIS：角鬥士
  - K'RATCHEK：戰士／德魯伊／靈能師（Fighter/Druid/Psionic）
  - CERMAK：保育師／角鬥士（Preserver/Gladiator）
  - CILLA：保育師／德魯伊／盜賊（Preserver/Druid/Thief）

  四位角色、單職／雙職／三職三種排列組合都測過，文字清晰、「／」
  分隔正常、無亂碼、無當機。

## 2. 為什麼要 6 個 patch 點，不是 1 個

職業繪圖函式（`5B7C:2DC1`，overlay 25，`file_start=0x6FDD0`）依「目前
有幾個職業」分成三條**各自獨立**的路徑，每條路徑對每一個要畫的職業
欄位都**重複**一次「讀 `record+0x21/0x22/0x23`→查表→push 遠指標」的
17-byte 區塊：

| 路徑 | 用到的欄位 | 出現次數 |
|---|---|---|
| 單職（`2F1F`） | 欄位1 | 1 |
| 雙職（`2EC9`起） | 欄位2、欄位1 | 各1 |
| 三職（`2E56`起） | 欄位3、欄位2、欄位1 | 各1 |

三條路徑合計：欄位1 出現 3 次、欄位2 出現 2 次、欄位3 出現 1 次，共
6 個實體 patch 點（座標分別是 `0x72C26`／`0x72C42`／`0x72C60`／
`0x72C99`／`0x72CB7`／`0x72CEF`）。**同一個欄位在不同路徑裡的組合
語言雖然重複，位元組不完全相同**（第一次出現時多半用 `les bx,
[bp+0xA]`，之後重複讀同一個記錄時省成 `mov bx,[bp+0xA]`，因為 `ES`
已經是對的），但功能等價，所以 6 個 patch 點可以共用同一批 FONT 端
解碼器——只需要 3 個（`class_slot1_label_entry`／`class_slot2_label_
entry`／`class_slot3_label_entry`，各自讀 `+0x21`／`+0x22`／`+0x23`），
不是 6 個。

每個 patch 點都是 3-byte `mov ax,<slot tag>` ＋ `re_89` 驗證過的
14-byte `ds_relative_consumer_redirect_bytes`（overlay-local IP，`push
cs` 自動抓住當下 segment），跟 HP:/PSI: 同一招，只是這次重複套用了
6 次、對應 3 個共用的 FONT 端進入點。

## 3. 職業名稱表（FONT-local，`class_offsets`，比照 `race_offsets` 的
可變長度 offset table 風格）

| 職業 ID | 英文 | 中文 |
|---|---|---|
| 1–4 | Cleric | 牧師 |
| 5–8 | Druid | 德魯伊 |
| 9 | Fighter | 戰士 |
| 10 | Gladiator | 角鬥士 |
| 11 | Preserver | 保育師 |
| 12 | Psionic | 靈能師 |
| 13–16 | Ranger | 遊俠 |
| 17 | Thief | 盜賊 |

新增 6 個字形（牧／魯／育／俠／盜／賊），全部落在 bank 5（跟種族/
陣營新增字同一個 bank），從 44 個字擴充到 50 個。ID 18-20（對應英文
池子裡「 MAGE」「CLERIC」「PSlONlC」這三個沒在實機見過的字串）
維持原文不動。

## 4. 尚未完成

- 等級、經驗值、DAM: 標籤（見 `re_88`）。
- 職業旁邊的等級數字（`5FB0:1A01`）本身不需要翻譯（純數字），已在
  `re_88` 第 6.6 節確認。

## 5. Hashes

```text
v68b DSUN.EXE
78a7f1bab8b168f97bafc0b0574b9365ee3d5474010cbdd02c93b9a03b36f4d9
v68b RESOURCE.GFF
8406e80875998466b53bac6d97a65da5823473ba1f4372141c6fbf2b6e5056e2

v68c DSUN.EXE
3eaabd6208c6d337bf21518bb61a4e29f3421495173b57afd8a9e3e7c6957542
v68c RESOURCE.GFF（跟 v68b 相同，本版沒有動 FONT/RESOURCE）
8406e80875998466b53bac6d97a65da5823473ba1f4372141c6fbf2b6e5056e2
```

建置腳本：`tools/build_view_class_names_slot1_candidate.py`（v68b，
parent 為 v67）、`tools/build_view_class_names_full_candidate.py`
（v68c，parent 為 v68b）。已淘汰、不要使用的失敗版本：
`tools/build_view_class_names_candidate.py`（純資料表 patch，見
`re_90`）。
