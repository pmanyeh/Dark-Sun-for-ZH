# DSUN 客體原生 Hires 對話文字 checkpoint

日期：2026-09-14

## 結論

繁體中文對話選項已由 DSUN 客體內的 16-bit assembly renderer 直接畫入
VBE `0100h` 640×400×8bpp framebuffer。執行時不需要 Tk、Pillow、第二個合成視窗，
也沒有修改 DOSBox-X。Pillow 只在建置階段把字型轉成固定 bitmap 資產。

可測候選版：

```text
D:\git\dsun-hires-text-poc\v9\runtime-native-text2
D:\git\dsun-hires-text-poc\v9\launch-native-renderer.cmd
```

## Guest asset

遊戲目錄新增 `HIRES.DAT`，34,082 bytes：

- signature：`DSHRT001`；
- 377 條對話翻譯；
- 844 個不同字元；
- 12×12、每列 16-bit mask、每 glyph 24 bytes；
- 英文原文以 32-bit FNV-1a 索引，建置時確認無 hash collision；
- 翻譯序列直接儲存 glyph index，不重複保存 Unicode 字串。

DSUN 第一次進入對話時以 DOS `INT 21h` 開啟並讀取 `HIRES.DAT`，資料存入 EMS
logical pages 9–12。這是遊戲資料資產，不是額外 renderer process。

## EMS 配置

目前共配置 13 個 16KB EMS pages：

- 0–3：Mode X A000 snapshot；
- 4–7：Mode X A400 snapshot；
- 8：VGA DAC palette；
- 9–12：`HIRES.DAT` translation/glyph asset。

## Renderer

VBE background 2× scale 完成後，renderer 逐一處理 dialogue queue：

1. 接受 `surface=3, x=3, y>=13` 的選項命令；
2. 對原始 Latin-1 bytes 計算 FNV-1a；
3. 在 EMS translation table 找 glyph sequence；
4. 依原選項座標轉成 640×400 座標；
5. 直接向 banked `A000` window 畫 12×12 glyph；
6. glyph row 若跨 64KB VBE bank boundary，立即切換 bank；
7. 使用 DSUN palette index `2Dh`，實測 RGB `(255,166,0)`。

SAVE01 門上 NPC 的六條回答均成功顯示，且每次測試後可以還原 Mode X、palette、
雙頁 framebuffer，dialogue queue 仍為 active 並保有六條命令。

證據：

- `artifacts/native-dsun-dialogue-vbe.png`；
- `artifacts/native-dsun-dialogue-restored.png`；
- `artifacts/native-dsun-presenter.json`。

## FONT 空間

native dialogue queue 的容量由 24 降為 8。實際 EBOX 可見選項為六列，且 queue 依
座標 upsert，8 records 仍保留兩格餘量。這釋出 2,688 bytes，使 FONT 為
29,868 bytes，低於已確認的 `0x8000` loader 邊界。

一般 v9 dialogue queue 仍維持 24 records；decoder 現可依 mailbox 長度安全辨認
1–24 records。

## 尚未完成

- EBOX 標題 `WHAT DO YOU SAY?` 走 `GuiPrintString/COUT`，尚未轉成 Hires；
- speaker/body 的 `^xx` CJK transport command 尚未由 native renderer 畫出；
- hourglass cursor 目前已烘焙在 Mode X background，尚未清除並作最後一層重畫；
- 右側 `MORE` 與箭頭仍是原始低解析 UI；
- presenter 仍以測試用 `INT 16h` 暫停，尚未進入持續互動模式。
