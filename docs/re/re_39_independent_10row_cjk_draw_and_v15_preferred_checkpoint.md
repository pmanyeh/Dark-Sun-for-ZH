# 9-row 排版／10-row 中文繪製與 v15 優先方案

> 日期：2026-08-15  
> 延續：`re_38_ebox_line_gap_pagination_and_ui_feedback_proof.md`

## 結論

不建立 SDL overlay，也能把原生 EBOX 的 9-row layout 與 CJK glyph 的實際 draw
height 解耦。v13/v15 使用 10×10 CJB1 record：前 9 列保留 Fusion Pixel 10px 主字形，
第 10 列容納完整的右下陰影；ASCII、FONT 全域高度與 EBOX 排版仍維持 9 rows。

實機確認此方案具有：

- 完整中文下緣與陰影；
- 原尺寸清晰度；
- 正常行距、`MORE` 分頁與返回。

## renderer patch

原 renderer 由 FONT global height 取得 9。安全 code cave `36AA:53D6` 新增 height
helper；marker byte `0x7F` 回傳 10，其餘 glyph 回傳 9。CJB1 record 從 92 bytes
增為 102 bytes，resident loader 機器碼長度不變，仍完整落在
`36AA:545A..5533`。

## v13/v14 A/B

v13 將所有 `0x7F` draw/clip path 視為 10：中文完整，但 `MORE` 不再提供變色回饋。

v14 嘗試只讓 resolver 的 word `0x017F` 使用 10，`0x007F` 保持 9。實機結果是
`MORE` 變色恢復，但中文第 10 列再次被裁切。這證明還有 UI／clip 高度查詢共用
`0x007F` 路徑，不能只在 glyph argument 層區分。

## v15 優先 checkpoint

```text
scratch_test/cjk_display_staging_v15_preferred_complete_text
```

目前以閱讀完整性優先，採用 v13 行為：中文不裁切、分頁可用，暫時接受 `MORE`
不變色。視窗採原生 640×480 的整數 2× 放大，即 1280×960。

```text
patched EXE SHA-256
15e8f818bb7a69fa972543c5bd5799717d245db8ca2a1c89eede6d1b59dc4ba0

patched RESOURCE SHA-256
4a8fe1be2a4161622545d39c50d54d3312a4e60afed44aa49c621f349601c726
```

29 項自動測試通過。`MORE` 色彩回饋列為後續 polish；若要恢復，應定位共享的
clip-height query／control redraw 狀態，不應退回 9-row CJK 或改用 SDL overlay。
