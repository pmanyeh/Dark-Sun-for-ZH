# FONT-100 16×15 中文字型實機驗證

> 日期：2026-08-14  
> 結果：成功  
> 前置文件：`re_12_multiglyph_chinese_phrase_and_resolution_limit.md`

> 2026-08-15 範圍修正：本證明只成立於當時的單一 probe。直接套用全域 15-row
> FONT，遇到 GPL 多個連續 `print` 組成的四行文本時，會產生不可翻頁的內容缺漏；
> 在 paginator 或 layout 尚未一併修改前，不能作為目前的可玩版預設。15-row
> rendering 本身仍保留為研究與精進方向。詳見
> `re_33_global_font_height_text_loss_and_9row_recovery.md`。

## 1. 結論

原版 *Dark Sun: Shattered Lands* renderer 已在 DOSBox-X 實機測試中成功接受：

- `FONT-100` 全域高度由 9 改為 15。
- 原英文 glyph 保留原始 9-row pixel data，垂直置中並補至 15 rows。
- 六個中文字使用 16×15 pixel bitmap、16-pixel advance。
- 同一行混合 16-pixel 中文與原版可變寬英文。

開場畫面成功顯示「中文顯示成功」，六字筆畫相較 8×9 版本明顯完整，沒有上下裁切。其後 `CJK 16X15` 英文正常顯示；後續行沒有因全域行高增加而互相重疊，遊戲也沒有崩潰。

## 2. 實驗配置

暫用單位元組映射沿用已避開 `%&` 的第二版：

```text
@ # $ [ ] *
↓ ↓ ↓ ↓ ↓ ↓
中 文 顯 示 成 功
```

GPL-2 第一段測試文字維持與原句相同的 58 bytes，避免改變後續舊式絕對 branch offset：

```text
@#$[]*  CJK 16X15 TEST....................................
```

測試 FONT 參數：

```text
glyph_count = 256
glyph_height = 15
ASCII source rows = 9（置中補空白）
CJK width = 16
CJK height = 15
CJK advance = 16
pixel palette = 0x00 / 0xFE
```

封裝後從 `RESOURCE.GFF` 回抽的 FONT payload，以及從 `GPLDATA.GFF` 回抽的 GPL-2，均與封裝輸入逐 byte 相同。

## 3. u5-cht 的採用範圍

本次採用了 `D:\git\u5-cht` 所記錄的下列設計：

- 中文使用 16×15 的 DOS 點陣尺寸。
- 中文 advance 採雙寬概念。
- ASCII 與 CJK 使用不同 glyph 尺寸，但共用一致的度量與繪製入口。

該 clone 含 MIT 授權的 `tools/build_eten_font.py`、Big5 分區索引、字型載入與排版方法，但刻意不含倚天 `STDFONT.15`、`SPCFONT.15` 或生成後 atlas。倚天點陣字庫屬原權利人，不隨 u5-cht 散布。

因此本次 glyph 暫由本機 `C:\Windows\Fonts\mingliu.ttc` 直接產生 16×15 bitmap，只存在 Git 忽略的測試目錄，不納入專案。若日後有合法自備的倚天字庫，可沿用 u5-cht 的 Big5 索引工具替換 glyph source，不必改變 Dark Sun 的 FONT/GFF 管線。

## 4. 已證明與未證明

### 已證明

1. FONT header 的 `height` 會被原版 renderer 採用，不是只能為 9。
2. FONT record 的 `width` 至少可達 16，不受原版 7-pixel 最大值限制。
3. 16×15 中文可讀性足以作為正式方案的起點。
4. 原英文 9-row glyph 可安全放入 15-row font。
5. 中英文不同寬度可以在原版 renderer 中混排。
6. 開場對話框可容納 15-pixel 行高，沒有立即發生裁切或行重疊。

### 尚未證明

1. 所有 UI、選單、物品欄與戰鬥訊息是否都使用同一個 FONT／行高路徑。
2. 自動換行是否在所有長度邊界都依實際 glyph width 計算。
3. 置中、右對齊、文字輸入框與游標是否支援 16-pixel CJK。
4. 如何讓超過 256 個中文字被索引。
5. 標準 Big5 bytes 是否會與 GPL／格式控制碼衝突。

## 5. 下一個主線：雙位元組 glyph lookup

單位元組實驗已完成使命。繼續替換 256 個 slots 無法支援全遊戲，因此下一個里程碑是：

```text
ASCII byte (< 0x80)
    → FONT-100 原英文 glyph

CJK lead byte + trail byte
    → 合成中文字索引
    → 外部 CJK font bank
    → 16×15 glyph、advance 16
```

實作順序：

1. 在 DOSBox-X 中對已知 `@`／「中」的 glyph record 或 pixel buffer 設 memory breakpoint。
2. 從觸發點回追 glyph offset lookup、width 讀取與 pixel blit 函式。
3. 找出呼叫端如何推進字串 pointer，以及是否存在 format/control-byte parser。
4. 先實作一組固定的雙位元組測試碼，只映射到「中」。
5. 確認兩個輸入 bytes 只消耗一個 glyph、advance 16，且換行寬度正確。
6. 再選擇標準 Big5 或避開保留碼的自訂 DBCS，並接上完整 CJK font bank。

由於第一輪 `%&` 曾在執行期被吞掉，正式編碼前必須先盤點控制碼，不能直接假設全部 printable／high bytes 都可安全使用。
