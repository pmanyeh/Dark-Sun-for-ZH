# v39 Load Game 閃退：全域字高控制碼衝突

> 日期：2026-09-09

## 結果

交叉控制組證明 v39 的 FONT-100 擴充與內嵌 633-byte core 本身可正常進入
Load Game；只在 v33 EXE 加入以下 27 bytes，則點選 Load Game 就會閃退：

```text
51F1..5201  extended height helper
53D6..53E0  near redirect
```

新 helper 把 byte `0x01..0x07` 全部當成 10-row 動態中文字形。Load Game 流程
顯然也使用這些既有控制碼；全域改變其字高語義會在 NAME trampoline 執行前破壞
載入流程。這解釋了為何 `36AA:5414` breakpoint 從未命中。

## v40 方針

撤回 extended helper 與 redirect，完整保留 v33 的 global height helper。NAME
動態槽 `0x01..0x07` 暫時依原行為繪製 9 rows；先驗證 Load、四個 consumer、
FONT-local core、CJB1 I/O 與 stack ABI。若能正確顯示但底列被裁切，再尋找只作用
於 NAME renderer 的局部高度方案，不再改變全域控制碼語義。
