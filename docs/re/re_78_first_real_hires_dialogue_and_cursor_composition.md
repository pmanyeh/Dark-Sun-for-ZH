# First real Hires dialogue and cursor composition

日期：2026-09-13

## 結論

SAVE01 門上方 NPC 的真實 GPL/EBOX 對話已由 Hires renderer 顯示。這一版不是在模擬畫面填入假資料：文字來源是已置入遊戲執行路徑的 `POC9DLG1` queue，原 `GgPrintString` 僅在確認對話 scope 後被抑制。

遊戲端仍負責 EBox、portrait、世界畫面、response 狀態與互動；host compositor 在最終 960×720 畫布直接 rasterize Noto Sans TC。DOSBox-X renderer 未修改。

## Scope 安全條件

`GuiInitEBox` 只建立 provisional tracking。第一個 `GgPrintString` 同時符合以下條件才確認為對話：

- `surface_id = 3`
- `x = 58`
- `y = 6`

確認前不抑制任何字，因此讀檔選單等共用 EBox 使用者保持原狀。確認後 `GuiEBoxSetText` 取代批次；`GuiKillEBox` 清空並結束 scope。

## 中文輸出

- Base94 transport 依 append-only `cjk_mapping` 解碼為 Unicode。
- 英文 response 依 localization catalog snapshot 對應現有繁體中文翻譯。
- 字型是 Noto Sans TC Regular，直接以最終實體 pixel size rasterize。
- NPC 多行回覆保留遊戲提供的各行座標。

## Cursor 最後合成

實測證實，單純在 captured frame 後畫 Hires 字會讓文字覆蓋遊戲游標。

修正後由遊戲資料讀取：

- `DS:A137/A139`：游標座標。
- `DS:A167`：cursor frame index。
- `DS:A16F`：live cursor bitmap far pointer。

compositor 解碼 DS1-RLE cursor，將 palette index 0 視為透明，只在 Hires 字完成後重貼非透明 pixels。因此順序是：

`低解析遊戲圖形 → Hires Text → 遊戲 cursor → present`

沒有矩形背景洞，游標移到文字上仍完整位於最上層。

## 證據

- `D:\git\dsun-hires-text-poc\v9\artifacts\dialogue-hires-initial.png`
- `D:\git\dsun-hires-text-poc\v9\artifacts\dialogue-hires-response-1.png`
- `D:\git\dsun-hires-text-poc\v9\artifacts\dialogue-hires-cursor-over-text.png`
- `D:\git\dsun-hires-text-poc\v9\artifacts\dialogue-command-queue.json`

`launch-poc-v9.cmd` 現在啟動隔離的 `runtime-dialogue-queue`，原 `runtime` 不覆寫。73 項 unit tests 與真實 Tk/worker/input UI smoke 均通過。
