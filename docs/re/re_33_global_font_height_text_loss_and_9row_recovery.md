# 全域 FONT 高度造成文本缺漏與 9-row recovery

> 日期：2026-08-15  
> 前置：`re_32_verified_chinese_display_staging_build.md`  
> 結論：目前直接套用全域 15-row FONT，會讓 GPL 多指令組句出現不可翻頁的文本缺漏；現階段安全 staging 維持原生 9-row layout，但 15-row 仍保留為待改良方案

## 1. 使用者發現的阻斷性 regression

同一段開場在原版 9-row FONT 可於一個對話框顯示四行：

```text
This day the mage Celgor will battle a
fearsome rampager. Watch and enjoy!
Do not worry, Gerakis. Your turn will come
soon. Stand back and watch the battle.
```

全域 FONT 高度改成 15 後只顯示前兩行。右側畫出 `MORE`，但使用者點擊後無法
翻頁，後兩行完全不可達。這不是單純「每頁文字變少」，而是遊戲內容缺漏。

## 2. GPL 結構原因

該畫面不是一個長字串，而是 GPL-2 在 offset `0x2536..0x25A1` 連續執行：

```text
0x2536 print "This day ... rampager. "
0x256F print "Watch and enjoy! "
0x2584 printnl
0x2585 printnl
0x2586 print "Do not worry, "
0x2599 print <Gerakis name expression>
0x25A1 print ". Your turn ... battle."
```

9-row 時整組輸出落在同一頁。15-row 時，overflow 恰好跨到後續 `print` 指令；
EBOX 畫出 MORE 狀態，卻沒有建立可由 UI 切換的下一頁。因此先前單一 probe 字串的
MORE/回頁成功不能外推到所有 GPL 多指令組句。

## 3. 排除 FONT padding 的 A/B

第一版 clean staging 在合法 FONT records 結尾 `0x32AD` 與固定 scratch
`0x3640` 間放入 915 個 padding bytes。這本身違反嚴格 FONT record 邊界，必須撤回。

為隔離變因，A/B 版換回先前 MORE 成功、records 恰好結束於 `0x3640` 的 probe
FONT，其餘 EXE、GPL、SPIN 與啟動方式不變。使用者再次確認後兩句仍然缺漏。

因此：

- 非法 padding 是獨立 builder bug，但不是這次文本缺漏的主因；
- 主因是全域 15-row layout 遇到多個連續 GPL print 的 overflow boundary。

## 4. 安全架構修正

`cjk_scratch_cache.asm` 的兩個常數已參數化：

```text
scratch_offset
cjk_record_bytes
```

安全 builder 現在要求：

```text
CJB1 glyph height == 原 FONT-100 global height
```

若 bank height 為 15、原 FONT 為 9，目前的 safe-profile builder 會直接拒絕，
不再未經標示地改變全域 layout。這是現階段安全閘門，不是永久禁止 15-row。
FONT scratch 緊接在原始合法 payload 結尾，不加入 padding。

## 5. Fusion Pixel 10×9 recovery build

`Fonts/Fusion_Pixel_10px.ttf` 自報名稱為：

```text
Fusion Pixel 10px Mono zh_hant Regular
```

抽查多個繁中字的 bitmap 均不同，排除 missing-glyph fallback。以 font size 10
rasterize 時，CJK 實際尺寸為 10×9，適合維持原生 layout。

新 bank：

```text
height             9
advance           10
record bytes      92  (u16 width + 10*9 pixels)
active glyphs    881
banks               4
```

各 bank：

```text
C0  24,592 bytes  1971bc2091ca1b398d85598740e874d8e9f62f6d91236d295fc375644d548a14
C1  24,592 bytes  86c478f0f3dbe1a72fb5e162d0a927e74bc648967e5f4ed450f9fa14cbd6fc52
C2  24,592 bytes  8cf3fb78bcc69b562508ba831794b12045bc77716dfd4f2d46a82ec44896d824
C3  10,864 bytes  bb11752c3b9a73135c81b56b3e373be550a50ec1ac0dd2ac176ed84350d9a417
```

新 staging contract：

```text
FONT global height       9（完全不改）
legacy FONT bytes     8299（完全不改）
scratch offset        8299 / 0x206B
scratch record bytes    92
```

輸出：

```text
scratch_test\cjk_display_staging_9row_v2
```

patched EXE SHA-256：

```text
4027493c8843b5aba76322e4a78446c2a95ac938e3b3725e60d681cfc21f7570
```

patched RESOURCE SHA-256：

```text
32a5a88235850690ceb662e67262edc1138926d95aeea0763049ae35558c10c7
```

RESOURCE 仍通過 173 個 target、1031 個 non-target chunk 驗證；19 項自動測試通過。

## 6. 使用者實機確認

新 staging 已由原廠三份 conf、`cycles=fixed 7000`、`DARKSUN.BAT` 啟動。使用者
在同一個開場畫面確認：

```text
四行文字已出現
```

因此下列 recovery checkpoint 已通過：

1. 開場四行全部恢復；
2. 原本被隱藏的 Gerakis 後續文本重新可見；
3. 不再依賴假的、不可點擊 MORE；
4. 原生 9-row layout 與連續 GPL `print` 組句相容。

這將文本完整性 blocker 從「recovery candidate」提升為實機通過。下一個必要
checkpoint 改為法術說明 UI：

1. 確認 Fusion Pixel 10×9 中文可讀；
2. 確認 ASCII 數字、冒號與標點正常；
3. 確認中文法術長句的換行與 MORE 可操作；
4. 測同一段中文中的跨 bank glyph 切換；
5. 關閉再開啟法術說明，確認 cache 重讀與重畫正常。

在法術 UI 通過前，中文顯示 staging 仍不標記為完整驗收。

## 7. 15-row 保留研究方向

本次負面結果只推翻「改一個 FONT global-height 就能直接投入完整遊戲」的假設。
下列方向仍可能讓 16×15 成為主要對話字型：

1. **修正 GPL/EBOX paginator**：當 overflow 發生於下一個 `print` 指令時，真正建立
   可達的 page node，而不是只畫出 MORE。
2. **解耦 raster height 與 layout line height**：ASCII 保持 9-row metrics，CJK
   blitter 個別繪製 15 rows；再明確定義 baseline、上下溢出與相鄰行間距。
3. **調整對話框與每頁行數**：擴大文字區或重新計算 portrait/text bounds，使
   15-row 仍能容納足夠行數。
4. **依 UI 使用字型 profile**：主對話採 16×15，小型介面採 Fusion Pixel 10×9，
   renderer 根據 FONT resource 或 UI context 選擇 metrics。
5. **預先重組 GPL print run**：importer 將會共同分頁的連續 print 組成安全 buffer；
   此法需嚴格保留動態姓名、變數插值與 script side effects，風險高於修 paginator。

因此目前決策是「9-row 先恢復可玩性，15-row 另立研究 checkpoint」，不是將
16×15 永久排除。
