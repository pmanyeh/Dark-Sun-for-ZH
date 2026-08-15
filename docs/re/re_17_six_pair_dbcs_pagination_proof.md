# 六組雙位元組中文字與分頁回畫驗證

> 日期：2026-08-14  
> 前置文件：`re_16_two_byte_single_glyph_runtime_proof.md`

> 2026-08-15 範圍修正：MORE/回頁只證明當時 probe 的頁面結構。它不能外推到
> GPL 多個連續 `print` 跨越 15-row page boundary 的情況；後者會畫出 MORE 卻
> 沒有可達下一頁。詳見 `re_33_global_font_height_text_loss_and_9row_recovery.md`。

## 1. 結論

固定雙位元組實驗已由單字擴展到六個連續中文字，並通過 MORE 分頁與回頁重畫：

```text
輸入：~A~B~C~D~E~F
輸出：中文顯示成功
```

實機確認：

1. 第一頁「中文顯示成功」六字完整、順序正確且沒有錯位。
2. 點擊 MORE 後第二頁英文正常。
3. 點擊右上角箭頭返回第一頁後，六個中文字仍完整且位置不變。

因此目前 patch 不只在第一次繪製有效；EBOX 以既有文字 buffer 重新 layout／重畫時，
同一套雙位元組解碼仍能穩定運作。

## 2. 測試編碼

六組 pair 與既有 FONT-100 測試槽位如下：

| pair | glyph slot | 顯示 |
|---|---:|---|
| `~A` | `0x40` | 中 |
| `~B` | `0x23` | 文 |
| `~C` | `0x24` | 顯 |
| `~D` | `0x5B` | 示 |
| `~E` | `0x5D` | 成 |
| `~F` | `0x2A` | 功 |

測試字串由原本的六個單位元組 placeholder 改為十二 bytes。為避免改變 GPL chunk
長度，句尾 padding 同時縮短六 bytes：

```text
原：@#$[]*  CJK 16X15 TEST....................................
新：~A~B~C~D~E~F  CJK 16X15 TEST..............................
```

兩者均為 58 bytes；重新組譯後 GPL-2 仍為 9,792 bytes。

## 3. 多 pair lookup helper

三個入口仍是：

```text
36AA:094A  一般文字 renderer
36AA:07F8  NUL 字串寬度計算
36AA:09A2  格式字串 renderer
```

每個入口呼叫自己的 pointer-aware helper。helper 保留普通 ASCII；遇到 `~` 時，
只有 trail 落在 `A..F` 才查六-byte table，額外增加一次 pointer：

```asm
mov  al,es:[bx]
cmp  al,7Eh
jne  return
mov  al,es:[bx+1]
sub  al,41h
cmp  al,05h
ja   invalid_pair
push bx
mov  bx,5410h
cs:xlat
pop  bx
inc  word [bp+pointer_slot]
ret
invalid_pair:
mov  al,7Eh
return:
ret
```

共享 lookup table 位於 `36AA:5410`：

```text
40 23 24 5B 5D 2A
```

新測試版 DSUN.EXE：

```text
SHA-256 fb64930820424740051256bb0e99cdde2311bf6b9546a132e9d272d793b133b7
```

新 GPL-2 chunk 在重封裝後重新抽取，與 assembler 輸出完全相同：

```text
SHA-256 06774e8fe62470d841fe239bea0cbd25ef9d7d5c65cb8604cc07f0315ac45b89
```

反組譯重封裝後的 `GPLDATA.GFF:GPL-2`，亦重新取得原定的
`~A~B~C~D~E~F` 字串。

## 4. 證明範圍

本次新增證據：

1. 多組 pair 可以連續解碼，不依賴 pair 之間的 ASCII 分隔。
2. 六個不同 pair 可經 table 映射到六個不同 glyph slots。
3. 一般 ASCII 與 DBCS 可在同一行混排。
4. MORE 第二頁的純英文沒有被 `~A..~F` 規則破壞。
5. 回頁時重新執行 renderer／layout，DBCS 結果仍一致。

這仍是固定小表，尚未突破 FONT-100 的 256 個 glyph slots。下一個核心工作是讓
DBCS lookup 回傳 16-bit CJK glyph id，並讓 glyph renderer 從獨立 CJK offset
table／pixel bank 取得字模，而不是只重新導向既有 FONT-100 slot。

## 5. 下一步

1. 決定 CJK bank 的磁碟承載方式：擴充 FONT payload 尾端或新增自訂 GFF chunk。
2. 確認 FONT-100 loader 的 allocation size 是否只依 chunk length，能否安全保留 appended data。
3. 將 DBCS helper 的回傳值由 8-bit slot 擴展為 16-bit glyph id／record pointer。
4. 先加入第 257 個測試 glyph，證明確實離開原 256-slot table。
5. 再建立完整字庫索引與翻譯編碼器。
