# DSUN 原生 Hires 字體品質 checkpoint

日期：2026-09-14

## 結果

原生 DSUN renderer 已由 12×12 單色點陣升級為 14×14、2-bit coverage 字形。執行路徑仍完全位於 DSUN.EXE／RESOURCE.GFF 與 `HIRES.DAT`，不需要修改 DOSBox-X，也不需要外部合成視窗。

測試候選版：

```text
D:\git\dsun-hires-text-poc\v9\runtime-native-text-aa2
D:\git\dsun-hires-text-poc\v9\launch-native-renderer.cmd
```

## 字體與 rasterization

- 來源字體：`assets/NotoSansTC-Regular.ttf`（Noto Sans TC Regular）
- 先以 26px 灰階繪製，加入 1 個高解析度像素的 synthetic embolden
- 再用 Lanczos 縮至 14×14；等效加粗約半個最終像素
- 每列儲存兩個 16-bit bitplane，共 56 bytes／glyph
- guest renderer 將 coverage 0/1 保持透明、2 畫成 palette `A8h` 金棕、3 畫成 palette `2Dh` 亮黃
- 字距由 12 增至 14，原本 8 個 Mode-X y 單位的行距在 VBE 中為 16px，因此字高 14px、行間保留 2px

這不是 TrueType 在 DOS 內即時 hinting；字形仍在 build-time 預製。不過它不再是 12×12 的 1-bit mask，邊緣與筆畫已能使用覆蓋資訊，並避免直接放大造成的粗鋸齒。

## Guest asset

- signature：`DSHRT002`
- 377 筆翻譯
- 844 個唯一字元
- `HIRES.DAT`：61,090 bytes，仍小於單一 64 KiB EMS mapping
- FONT chunk：29,908 bytes，仍小於既有 loader 的 `0x8000` 邊界

## 驗證

- 全套 pytest：79 passed
- SAVE01 實際流程：眼睛游標點門上 NPC，五個中文選項均在 640×400 guest framebuffer 內完成繪製
- VBE frame：640×400，左右畫面完整，中文沒有跨行覆蓋
- 退出 presenter 後：正確還原 320×200 Mode-X 畫面、palette、兩個 page 與對話 mailbox

證據：

- `artifacts/native-dsun-dialogue-vbe.png`
- `artifacts/native-dsun-dialogue-restored.png`
- `artifacts/native-dsun-presenter.json`

## 尚未處理

- `WHAT DO YOU SAY?`、`MORE` 等固定 UI 字樣仍是原遊戲低解析度字體
- hourglass／mouse cursor 目前仍由切換前的 Mode-X 背景帶入，尚未做 Hires 層級的游標重畫與遮擋順序
- presenter 仍保留 `INT 16h` bring-up gate，供人工檢查後按鍵返回遊戲
