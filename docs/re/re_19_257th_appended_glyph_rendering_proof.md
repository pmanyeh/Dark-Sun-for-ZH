# 第 257 筆 appended glyph 實機繪製證明

> 日期：2026-08-14  
> 前置文件：`re_18_appended_cjk_bank_loader_proof.md`

## 1. 結論

Dark Sun 已成功從原 FONT-100 13,888-byte legacy payload 結尾之外，讀取並繪製
一筆 appended 16×15 中文字模。畫面仍完整顯示：

```text
中文顯示成功
```

其中第一個「中」由 `CJK1` extension record 提供；後五字仍來自原 256-slot
FONT records。使用者實機確認第一個「中」外觀正常，整句沒有錯位或當機。

這是本專案首次證明中文字模資料可以超出原始 256 筆 FONT records，並由原遊戲
glyph raster loop 正常繪製。

## 2. 最小路由方式

本次仍使用一個 legacy marker slot 作為過渡：

```text
DBCS pair ~A
  -> helper lookup result 0xFF
  -> glyph_offsets[0xFF] = 0x3650
  -> appended CJK1 record
```

`0x3650` 是相對 runtime FONT payload base 的 offset：

```text
legacy FONT payload length = 0x3640
CJK1 header length         = 0x0010
first appended record      = 0x3650
```

因此 record 明確位於 legacy payload 結尾之外，不可能是原 `0x40` 字模槽。

## 3. 動態斷點證據

在一般文字 helper 完成 pair lookup 後，斷點命中：

```text
CS:EIP = 36AA:53BE
AL     = FF
```

這證明 `~A` 已被消耗成單一 marker `0xFF`。接著將斷點移到原 glyph renderer
讀取 record width 之前：

```text
CS:EIP = 36AA:06FE
ES:BX  = 80E3:3654
```

runtime FONT payload base 為 `80E3:0004`，所以：

```text
0004 + 3650 = 3654
```

指標計算與預期 appended record 完全一致。

## 4. Record 完整性

從 `80E3:3654` 讀取 242 bytes：

```text
u16 width     = 16
pixel bytes   = 240
glyph height  = legacy FONT global height 15
```

執行期 record 與磁碟 `CJK1` record 逐 byte 相同：

```text
SHA-256 021773412299d41e22cece7590740c328cb851b23dacc70556b06cc694f633ff
```

隨後解除所有斷點並恢復遊戲，畫面完成繪製。第一個 appended「中」與後續五個
legacy glyph 外觀一致，證明原 `36AA:0761-07CB` raster loop 不在意 record
是否位於舊 FONT 尾端以內，只要 width／pixels 與 offset 有效即可。

## 5. 已突破與剩餘限制

已突破：

1. GFF loader 可載入大於 legacy FONT payload 的完整 chunk。
2. offset 可以指到 legacy 256 records 之外。
3. appended glyph 可使用原 width、palette map、pixel loop 與 advance。
4. DBCS pair 可選擇 appended 中文字模。

目前過渡實驗仍借用 `0xFF` marker 與 legacy u16 offset table entry，因此同時最多只能
借用有限的舊槽位，尚未形成完整中文字庫索引。

## 6. 下一步：真正的 16-bit CJK id（已由 re_20 推進）

正式架構應讓 pair lookup 直接產生 16-bit CJK glyph id，並走獨立 table：

```text
ASCII
  -> legacy FONT offset table

DBCS lead + trail
  -> 16-bit CJK id
  -> CJK1 offset table
  -> appended glyph record
```

最小下一版應先放入兩筆 appended glyph，讓兩組 DBCS pair 在完全不修改兩個
legacy offset entries的情況下，分別畫出兩個中文字。完成後即可把 table 擴展到
翻譯語料實際所需的字數。

結果見 `re_20_independent_cjk_id_table_six_glyph_proof.md`：六個 pair 已先形成
CJK ID `0..5`，再由獨立 CJK1 offset table 選取六筆 appended records。實作採
單一 `0x7F` runtime trampoline 相容原 renderer，不再需要一字占用一個 legacy slot。
