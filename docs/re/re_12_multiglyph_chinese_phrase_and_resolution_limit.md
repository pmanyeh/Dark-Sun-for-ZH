# 多中文字形顯示成功與 8×9 解析度上限

> 日期：2026-08-14  
> 結果：六個不同中文字均成功顯示；8×9 不適合作正式繁中字型  
> 前置文件：`re_11_font100_single_byte_chinese_glyph_proof.md`

## 1. 實驗目的

`re_11` 已證明把單一 ASCII glyph `@` 換成「中」後，原版 Dark Sun renderer 能正常繪製中文字。本次進一步建立自動化多字流程，驗證：

```text
UTF-8「中文顯示成功」
    → 系統中文字型 rasterize
    → 六個 Dark Sun FONT-100 glyph
    → 六個暫用單位元組 placeholder
    → GPL-2 對話
    → RESOURCE.GFF / GPLDATA.GFF
    → DOSBox-X 原版遊戲畫面
```

測試字形由本機 `C:\Windows\Fonts\mingliu.ttc` 產生，只用於本機實驗，不納入 Git。`tools/font100_tool.py replace-text` 現可接收 Unicode 字串、placeholder bytes、TrueType/OpenType 字型、rasterize 尺寸、輸出寬度與 threshold，並輸出可稽核的 mapping JSON。

## 2. 第一輪：發現可能的控制序列

第一輪使用：

```text
@ # $ % & *
↓ ↓ ↓ ↓ ↓ ↓
中 文 顯 示 成 功
```

GPL 與 FONT 從重新封裝的 GFF 回抽後，均與輸入逐 byte 相同；但遊戲畫面只顯示「中文顯功」，中間對應 `%&` 的「示成」消失。

因為兩個 glyph 都確實存在於 FONT atlas，且 `%&` 仍存在於 GPL chunk，消失發生在遊戲執行期文字處理。現階段只能確定 `%&` 這組 bytes 會被消耗或抑制，尚不能在未分開測試前斷言 `%` 與 `&` 各自的精確語意。

這是未來設計自訂遊戲內編碼的重要限制：不能只依「可列印 ASCII」判定 byte 可安全使用，必須先建立 renderer／formatter 的保留碼表。

## 3. 第二輪：六字完整顯示

第二輪改用：

```text
@ # $ [ ] *
↓ ↓ ↓ ↓ ↓ ↓
中 文 顯 示 成 功
```

遊戲畫面成功顯示六個不同的中文字，其後的 `CJK PHRASE TEST` 英文也正常。這證明：

1. 多個 Unicode 字元可以自動轉成 Dark Sun glyph。
2. 多個不同的暫用字碼可以在 GPL 對話中依序抵達 renderer。
3. FONT-100 可接受 9-pixel advance，原版上限為 7 的限制不是 renderer 的硬上限。
4. 英文與中文字形可以在同一行混排。
5. RESOURCE.GFF 與 GPLDATA.GFF 的雙資源回寫管線穩定。

## 4. 8×9 的品質限制

六字雖全部出現，但「顯」「成」等複雜字有明顯缺筆。這不是解碼遺失，也不是 renderer 漏畫，而是將細明體約 16-pixel 的方形中文字壓縮至 8×9，再二值化為 `0x00/0xFE` 時，細筆畫低於取樣 threshold 或合併在同一 pixel。

調低 threshold 只能讓字變得更黏、更糊；調高則會遺失更多筆畫。8×9 可用於辨識簡單漢字及證明管線，不適合作為全遊戲正式繁中字型。

## 5. 下一步

停止繼續微調 8×9，改做 16×15 字型與行高實驗：

1. 將 FONT payload 的全域 height 由 9 改為 15。
2. 原英文 glyph 保持既有 9-row 圖形，補空白至 15 rows。
3. 中文 glyph 使用 16×15 原生比例，advance 設為 16。
4. 測試 renderer 是否依 FONT header height 正確繪製、換行與推進。
5. 觀察對話框可容納行數、基線、上下裁切及行距。

若 16×15 能正常顯示，正式架構可採「ASCII 保留原字形、CJK 雙寬 16×15」；若原版對話框或行距函式不接受，就必須在定位 glyph blit 時一併修改 line-height／wrap 邏輯。

本次仍屬單位元組暫用槽實驗，尚未解決 256-glyph 容量。畫質實驗完成後，主線仍是定位 renderer，讓雙位元組或自訂索引能指向獨立 CJK font bank。
