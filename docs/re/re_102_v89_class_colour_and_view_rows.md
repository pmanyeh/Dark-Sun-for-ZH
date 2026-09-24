# re_102：v88c 第三職業顏色、v89 VIEW CHARACTER 下半部行距

> 日期：2026-09-24
> 前置：`re_94` §6（誤判為原生配色）、`re_95` §1（v75 座標）、`re_101`
> 產出：`scratch_test/cjk_display_staging_v89_view_rows`

## 1. 第三職業顏色（v88c，使用者實機確認）

### 1.1 原版的職業配色（`0x72D29`，16 項跳轉表在 `0x72D58`）

| 職業 ID | 職業 | 顏色 |
|---|---|---|
| 1–4 | 牧師（地／風／火／水） | 0x27／0x40／0x4D／0x38 |
| 5–8 | 德魯伊（同上） | 0x27／0x40／0x4D／0x38 |
| 9–12 | 戰士、角鬥士、保護者、靈能師 | 預設文字色 `ds:[326E]` |
| 13–16 | 遊俠（同牧師） | 0x27／0x40／0x4D／0x38 |

另外，若 `0430:0000` 的 dword 為 0，一律改用預設色。K'RATCHEK 的德魯伊（ID 7）是紅色 0x4D，
屬原版設計；靈能師（ID 12）應為預設色。

### 1.2 原因

多職業模板 `%C%C%C%s%C/%C%s%C/%C%s`，每個 `%C` 吃兩個 word（來源色、目標色），交給
`11A4:5956` 寫入 256 項的顏色對照表（沒有容量上限；re_94 的「顏色池」猜測不成立）。
三職業路徑：

```text
0x72C12  mov dx,ax                 ; DX = 職業3顏色
0x72C26  （17 bytes，v71 換成 class_slot3 redirect）
0x72C37  push dx                   ; 當成職業3的 %C 目標色
```

解碼器以 DX:AX 回傳字串指標，回來時 DX 是 FONT 的段位址，低位元組被當成色號，所以畫成洋紅色。
職業 1／2 之後讀的是 `[bp-2]`、`[3270]`、DI，不受影響，因此只有三職業的第三段出錯。

### 1.3 修法

`class_slot3_label_entry` 先把 DX 存到 `class3_saved_dx`，`class_slot3_decoded` 在 `lret`
前還原。模擬測試 `ClassSlotMachineTests.test_third_class_keeps_the_callers_colour_in_dx`
在修正前失敗、修正後通過。

### 1.4 位址換算更正

檔案位移 = `0x5400` + (執行期段 − `0x824`) × 16 + 偏移。例：`339E:016D` → `0x30D0D`。
re_94 當時用的 `0xD640` 是錯的，因此讀到的 `11A4:5956` 並不是真正的函式。

## 2. 下半部四行（v89）

| 行 | v75 | v89 | 控制位置 |
|---|---|---|---|
| 職業 | 106 | **108** | 解碼器（見下） |
| 等級／EXP | 115 | **118** | EXE `0x8A218`、`0x8A285` |
| 生命／靈能 | 125 | **128** | EXE `0x8A2D3`、`0x8A349`；標籤是 asm 的 `VIEW_STAT_ROW_Y` |
| 防禦／DAM | 138 | 138 | EXE `0x8A390`、`0x8A3C5` |

行距 10／10／10。使用者原本提的是「+2／+3／+2」，生命行多 1px 讓間距完全相同。

職業行的 `push dword 006A:0095`（`0x8A1E4`）與 overlay relocation 重疊，不能改。改由
`class_slot1_label_entry` 處理：職業函式把 Y 放在呼叫者的參數 `[bp+10h]`，之後才交給
formatter（formatter 的 `di=[bp+0Ch]` 就是 Y）。職業 1 每次繪製只解碼一次，且一定在
formatter 之前，所以在這裡若 `[bp+10h]==106` 就改成 108。設定在 `view_ui_layer.py` 的
`CLASS_ROW`／`LEVEL_ROW_Y`／`STAT_ROW_Y`／`ARMOUR_ROW_Y`。

測試注意：Unicorn 對「同一位址改寫程式碼」會沿用舊的翻譯快取，模擬測試裡每個 tag 的 stub
要放在不同位址。
