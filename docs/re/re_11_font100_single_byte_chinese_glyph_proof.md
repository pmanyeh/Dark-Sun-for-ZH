# FONT-100 單位元組中文字形實機驗證

> 日期：2026-08-13  
> 結果：成功  
> 前置文件：`re_10_opends_roundtrip_and_localization_catalog.md`

## 1. 本次突破

我們已在未修改 `DSUN.EXE` 的情況下，讓原版 *Dark Sun: Shattered Lands* renderer 在 DOSBox-X 中實際畫出中文字「中」。

實驗將 `RESOURCE.GFF:FONT:100` 的 `@`（字碼 `0x40`）glyph 替換為自製的 8×9「中」點陣，再將開場 Celgor 對話改為：

```text
@ FONT GLYPH TEST @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
```

遊戲畫面中所有 `@` 都一致顯示為「中」，其餘英文仍正常顯示，文字能正常換行，遊戲沒有因修改後的 FONT chunk 或較寬 glyph 而崩潰。

這項結果已實機證明：

1. `FONT-100` 是遊戲開場對話實際使用的字型資源。
2. `FONT-100` glyph 格式與 offset table 的解析正確。
3. palette index `0xFE` 可作為前景，`0x14` 可作為陰影。
4. 原版 renderer 能接受由 6 pixels 擴為 8 pixels 的可變字寬 glyph。
5. 修改後的 FONT chunk 可重新封裝進 `RESOURCE.GFF` 並被遊戲接受。
6. 中文點陣本身不需要修改 DOSBox code page，也能由遊戲的圖形 renderer 畫出。

## 2. FONT-100 格式

原始 `FONT-100` 大小為 8,299 bytes，解析結果如下：

```text
u16 glyph_count                  = 256
u16 glyph_height                 = 9
u32 reserved                     = 0
u8  character_map[glyph_count]   = 00, 01, ... FF
u16 glyph_offsets[glyph_count]   = payload 內的絕對 offset

glyph_record:
    u16 width
    u8  pixels[width * height]
```

原始 glyph 寬度為 0–7 pixels，只使用三種 pixel 值：

| 值 | 實驗用途 |
|---|---|
| `0x00` | 透明／背景 |
| `0x14` | 棕色陰影 |
| `0xFE` | 明亮前景 |

實驗工具位於 `tools/font100_tool.py`，可驗證格式、輸出 PNG atlas，以及將 `0x40` 替換為「中」：

```powershell
python tools\font100_tool.py info FONT-100.bin
python tools\font100_tool.py render FONT-100.bin font-atlas.png
python tools\font100_tool.py replace-zhong FONT-100.bin FONT-100.zhong.bin
```

## 3. 實驗完整性

原始與測試 FONT payload：

```text
DBC5528A43F03B8EC5C5DA61B53749ACBDE267C8CC0CC751332F0D78DAFF46A4  FONT-100 original
3CFFC65BC2E708779694360055E5E2A28C23EED70A81D35AA6ADDD714F9E555F  FONT-100 zhong-at-0x40
```

修改後的 `RESOURCE.GFF` 重新抽取 `FONT-100`，SHA-256 與測試 payload 完全一致。GPL-2 也重新反組譯確認測試句存在。為避免舊式 GPL 絕對分支 offset 因字串縮短而越界，測試句刻意維持與原句相同的 58 ASCII bytes。

所有遊戲修改都位於 Git 忽略的：

```text
scratch_test/font_zhong_experiment/
```

Steam 原始遊戲檔未被覆寫。

## 4. 尚未證明的部分

這次證明的是「一個 byte 可以索引並畫出一個中文字形」，尚未證明原版引擎能直接解讀 Big5 或任何雙位元組編碼。

原始 FONT 只有 256 個 glyph slots，即使重用高位元區，也不足以容納全遊戲所需中文字。因此單純替換 glyph 適合原型或極小字庫，不能直接成為完整中文化方案。

標準 Big5 也不能直接假設安全：若 renderer 逐 byte 查表，一個中文字會被當成兩個 glyph；此外 trail byte 可能落在 ASCII 範圍，字串長度與換行函式也仍以 byte 計算。

## 5. 下一步

下一階段應定位 `FONT-100` glyph lookup／blit 函式，建立最小的雙位元組解碼實驗：

1. 追蹤 `0x40` 如何從對話緩衝區變成 FONT offset table 索引。
2. 確認 glyph lookup、寬度累加與換行是否位於同一函式。
3. 先在記憶體或測試 EXE 中加入一組雙位元組 → glyph index 映射。
4. 讓兩個測試 bytes 只消耗一個中文字 glyph，並正確前進 8 或更多 pixels。
5. 再決定採標準 Big5，或由 UTF-8 manifest 建置成較安全的自訂 DBCS。

在 renderer 修改完成前，翻譯主表仍應保存 UTF-8；Big5 或自訂 DBCS 只作為建置時輸出，避免過早把翻譯資料綁死在尚未驗證的遊戲內部編碼。
