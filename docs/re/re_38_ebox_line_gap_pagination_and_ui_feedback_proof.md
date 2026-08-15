# EBOX 行距、分頁與 UI 回饋同步證明

> 日期：2026-08-15  
> 延續：`re_37_variable_length_gpl_dialogue_importer_and_v7_checkpoint.md`

## 1. 現象拆分

EBOX line-table 每行增加 2 pixels 後，實機畫面證明這項修改增加的是相鄰文字
baseline 的距離，不是 glyph bitmap 的可視高度。中文字下緣仍可能被原有 cell／clip
邊界裁切，因此「字形裁切」與「行距」必須作為兩個獨立問題處理。

同一畫面同時出現 `MORE`，證明原生 EBOX 已依 line table 的累積像素高度算出本頁
只能容納三行。換行、像素溢位、`MORE` 顯示與可見行範圍計算均可沿用，不需要為此
另建 SDL 文字層。

## 2. v9：溢位正確，但無法翻頁

```text
scratch_test/cjk_display_staging_9row_v9_layoutgap2
```

v9 保留原版五行翻頁行為。此對話共有四個 logical lines，而增加行距後本頁只顯示
前三行；下一頁事件仍送出 `-5`，共享捲動函式算出的目標超出總行數，依原生邊界
檢查拒絕更新 `EBOX object + 0x8A`。因此 `MORE` 會出現並有正常變色回饋，但按下後
頁面不動。

## 3. v10：翻頁成功，但錯改 UI 狀態

```text
scratch_test/cjk_display_staging_9row_v10_layoutgap2_page3
```

v10 將兩套 EBOX dispatcher 內四個 `mov si,5` 全部改成 `mov si,3`。下一頁因此成功，
但中文與英文 A/B 都失去 `MORE` 的 hover／按壓變色。這證明 `SI=5` 同時參與原版
控制項回饋路徑，不能直接當成純頁距常數修改。

英文對照版：

```text
scratch_test/cjk_display_staging_9row_v10_english_ab_gap2_page3
```

英文同樣不變色，排除 Base94、CJK glyph cache 與中文內容是成因。

## 4. v11：分離 UI 狀態與實際位移

```text
scratch_test/cjk_display_staging_9row_v11_layoutgap2_page3_ui5
```

正式修正保留四個原版 `SI=5`。只在兩個 next-page call site，把：

```asm
mov ax,si
neg ax
push ax
```

改為等長且不碰 `SI` 的：

```asm
push byte -3
nop
nop
nop
```

上一頁仍執行原版五次 `+1` 回退；從起始行 3 返回時，前三次到達 0，後兩次由原生
負值邊界檢查拒絕，因此不會越界。

## 5. 驗證結果

- 25 項自動測試通過。
- patched EXE SHA-256：
  `7507babbd2f08e22188eb36cf47879818fb08fe79be5c440085cc222dcfd15a4`
- 使用者實機確認 v11 的 `MORE` 黃色回饋已恢復。
- 先前 v10 實機已證明三行位移可到達剩餘文本；v11 使用相同 `-3` 位移，但不再改寫
  UI 的 `SI=5`。

## 6. 後續範圍

v11 解決的是 line-table 行距與原生 paginator／control feedback 的同步。中文字下緣
裁切尚未解決；下一階段應研究 glyph cell、baseline 與 clip rectangle，而不是繼續
增加 line gap。
