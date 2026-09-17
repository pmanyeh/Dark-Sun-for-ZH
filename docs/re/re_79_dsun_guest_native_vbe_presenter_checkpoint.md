# DSUN 客體原生 VBE presenter checkpoint

日期：2026-09-14

## 結論

第一個真正執行於 `DSUN.EXE` 流程內的 native presenter 已完成並通過 SAVE01
門上 NPC 對話實測。它不使用 Tk／外部合成視窗、不修改 DOSBox-X，也不要求特製
模擬器版本。

目前完成的是安全的顯示底座：DSUN 的 Mode X 雙頁與 DAC palette 會先保存到 EMS，
切換到 VBE `0100h`（640×400×8bpp）後，以 guest assembly 做 2× nearest-neighbor
輸出；測試按鍵後再完整還原 Mode X、兩個 page、palette 與 CRTC start address。

中文字形 renderer 尚未接入，因此已被 dialogue queue 抑制的 Gg 對話選項目前在
VBE 畫面中是空白。`WHAT DO YOU SAY?` 屬於另一條 `GuiPrintString/COUT` 路徑，仍以
原始低解析字顯示。

## 已驗證的 runtime 路徑

```text
GuiUpdatePages 36AA:0BA1
  -> FONT adapter（使用原 MZ far-call relocation）
  -> 原 show_page(-1) 11A4:5814
  -> 保存 A000 / A400 Mode X pages
  -> 保存 256 色 DAC palette
  -> VBE 0100h
  -> guest-native 320×200 -> 640×400 presenter
  -> 按鍵
  -> Mode X / palette / A000 / A400 / CRTC 全部還原
  -> 返回 GuiUpdatePages 36AA:0BA8
```

不能全域 hook `show_page`：遊戲啟動初期已會呼叫它，但 FONT resource 尚未初始化，
此時 FONT trampoline 的內部 far-call segment 仍為零。最終改掛已驗證的
`GuiUpdatePages` 呼叫點；這條路徑在 FONT/GUI 載入完成後才執行。

## 記憶體策略

使用 9 個 EMS pages：

- logical pages 0–3：A000 page 的 64KB chunky snapshot；
- logical pages 4–7：A400 page 的 64KB chunky snapshot；
- logical page 8：768-byte VGA DAC palette scratch。

四個 logical pages 會映射到 EMS 64KB page frame。這避免占用 DSUN 已緊張的
conventional memory，也不覆寫遊戲管理的 surface 5。

Mode X capture 已從逐像素切 plane 改為逐 plane 連續讀取：VGA plane-select I/O
由 64,000 次降為 4 次。

## FONT loader 邊界

實測 FONT resource 跨過 `0x8000` bytes 時，啟動早期 trampoline 的 resident far-call
segment 會保持為 `0000`。將 palette scratch 搬到 EMS 後，目前 FONT 為 32,124 bytes，
低於此界線；build test 會阻止再次越界。

## SAVE01 實測證據

`artifacts/native-dsun-presenter.json`：

- VBE frame：640×400，127 colors；
- restore frame：320×200，108 colors；
- FONT pointer：`80E3:0004`；
- dialogue mailbox：`80E3:6814`，signature `POC9DLG1`；
- queue：`active=true`、generation 4、6 commands；
- cursor command/bitmap 仍可讀取。

畫面：

- `artifacts/native-dsun-dialogue-vbe.png`
- `artifacts/native-dsun-dialogue-restored.png`

## 下一階段

1. 將 dialogue translation 與實際 glyph bitmap 資產放入 guest 可載入的資料區；不能再
   持續擴大 FONT，因為只剩很小的 `0x8000` loader 安全空間。
2. 在 VBE 2× background 完成後，依 `dialogue_commands` 畫真正的高解析中文字。
3. 清除／避免把舊 Mode X cursor 烘焙進背景，最後才依 queue 中的 cursor bitmap 以
   2× 座標重畫，驗證游標覆蓋文字的層級。
4. `show_page` 並非 hover 的唯一更新點；完成對話 renderer 後仍需為 direct-visible
   hover/tooltip 建立 dirty/present 路徑。
