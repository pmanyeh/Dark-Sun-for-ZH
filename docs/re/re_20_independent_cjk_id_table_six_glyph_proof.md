# 獨立 CJK ID／offset table 六字實機驗證

> 日期：2026-08-14  
> 前置文件：`re_19_257th_appended_glyph_rendering_proof.md`

## 1. 結論

六組雙位元組 pair 已不再分別映射到六個 legacy FONT slots。新版 resolver 先形成
CJK ID `0..5`，由 `CJK1` extension 的獨立 offset table 選出六筆 appended
records，再透過單一 legacy marker `0x7F` 相容 trampoline 交給原 renderer。

```text
~A..~F
  -> CJK ID 0..5 (16-bit AX index)
  -> CJK1 independent u16 offset table
  -> six appended 16×15 records
  -> one temporary marker slot 0x7F
  -> unchanged legacy glyph renderer
```

實機畫面完整顯示「中文顯示成功」，六字順序與外觀均正確。

此架構仍保留一個 marker 作為相容 trampoline，但字庫容量不再等於可借用的 legacy
slots 數量：所有 CJK glyph 共用同一 marker，實際 identity 與 record selection
均來自獨立 CJK table。

## 2. CJK1 六字 bank

新版 `tools/build_font100_cjk_probe.py` 建立：

```text
CJK1 header          16 bytes
u16 offsets[6]       12 bytes
six glyph records  1452 bytes
extension total    1480 bytes
```

完整 FONT payload：

```text
legacy FONT-100    13,888 bytes
CJK1 extension      1,480 bytes
total              15,368 bytes
SHA-256 d583d985978d1cf424ffc7ca3f2674ad99841e69a556552935dca893974a7d72
```

legacy offset table 在磁碟檔中保持不變；`0x7F` entry 只在每次解析 CJK pair 時於
執行期暫時更新。

## 3. Resolver 與相容 trampoline

三個文字入口仍以 near call 進入各自的 pointer wrapper。wrapper 呼叫共同 resolver
`36AA:5420`：

1. 普通 ASCII 原值返回。
2. `~A..~F` 轉成 CJK ID `0..5`。
3. 將 ID 乘二，查 `payload+0x3650` 的獨立 u16 offset table。
4. 加上 CJK1 base `0x3640`，得到 payload-relative record offset。
5. 將該 offset 暫寫入 runtime legacy `glyph_offsets[0x7F]`。
6. 回傳 marker `0x7F`，由未修改的 glyph lookup／width lookup 繼續處理。

wrapper 另外根據 pair flag 多增加一次各自的文字 pointer，因此仍是兩 bytes 只消耗
一個 glyph。

固定後的測試版 DSUN.EXE：

```text
SHA-256 e7aec86e31ed4de2585b022473f14791c9253efb6b2ae58ce52062e4c5470bb7
```

## 4. 六筆動態記錄

在 resolver 寫入 trampoline 的 `36AA:5457` 與原 renderer 讀取 width 的
`36AA:06FE` 交錯設斷點，得到：

| Pair | CJK ID | Payload-relative offset | Runtime record | Width |
|---|---:|---:|---|---:|
| `~A` | 0 | `0x365C` | `80E3:3660` | 16 |
| `~B` | 1 | `0x374E` | `80E3:3752` | 16 |
| `~C` | 2 | `0x3840` | `80E3:3844` | 16 |
| `~D` | 3 | `0x3932` | `80E3:3936` | 16 |
| `~E` | 4 | `0x3A24` | `80E3:3A28` | 16 |
| `~F` | 5 | `0x3B16` | `80E3:3B1A` | 16 |

觀察到兩個階段：width/layout pass 先連續解析 ID 0～5；實際 glyph pass 再次逐字
解析相同 ID，並在 `06FE` 取得上表六個不同 record pointers。這同時證明 layout
與繪製共用獨立 table 的選字結果。

## 5. Off-by-base 修正

第一版 common resolver 曾把 runtime payload base offset `+4` 加進 trampoline entry；
原 glyph lookup 隨後又自行加一次 `[A378]`，造成 record pointer 多四 bytes。動態
斷點在任何錯誤像素被畫出前發現：

```text
錯誤第一筆：0x3660
正確第一筆：0x365C
```

已移除 resolver 內重複的 base addition，保留四個 NOP 以維持所有 helper 位址：

```text
36AA:544B = 90 90 90 90
```

當次執行期先熱修正並成功顯示六字；之後關閉 DOSBox、重新安裝磁碟補丁並重啟，
再次確認磁碟與 runtime `36AA:544B` 均為四個 NOP，完整 72-byte resolver 逐 byte
一致。

## 6. 容量模型與下一步（跨 bank 已完成）

目前 CJK ID 已在 resolver 內以 16-bit `AX` 參與索引；單一 CJK1 bank 的 record
offset 仍是 u16，因此 bank 本身須控制在 64KB 內。可擴展方案為：

```text
u16 CJK ID
  high bits -> bank number
  low bits  -> glyph index within bank
```

每個 bank 使用自己的 u16 offset table、大小不超過 64KB；多個 bank 可串接在
FONT chunk 尾端，resolver 依 high bits 選 bank。下一步應以第二個 bank 或跨越
255 的 CJK ID 做實驗，並用實際翻譯 catalog 統計所需 unique Han characters，決定
bank 大小與編碼分配。

跨 255 實驗已由 `re_21_cross_255_cjk_id_multibank_proof.md` 完成：CJK IDs
`256..258` 成功選取 bank 1 並正常繪製「示成功」。下一步轉入正式字庫與翻譯
編碼管線。
