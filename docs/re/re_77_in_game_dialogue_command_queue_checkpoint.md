# Native Hires Text：遊戲內對話命令 Queue checkpoint

日期：2026-09-13

## 結論

第一個真正置入 `DSUN.EXE` 執行路徑的旁路元件已完成。它不改變原文字輸出，僅在遊戲自身的 FONT 配置記憶體中維護對話文字命令 queue。

這證明中央輸出點不只可由 debugger 觀察，也能由原遊戲程式安全攔截並建立可供後續 Hires renderer 使用的持久狀態；不需修改 DOSBox-X。

## 已攔截入口

- `GuiInitEBox`：建立新對話 scope。
- `GuiEBoxSetText`：開始新的文字批次並取代上一批。
- `GgPrintString`：以 `(surface_id, x, y)` upsert 實際文字。
- `GuiKillEBox`：關閉 scope 並立即清空命令。

所有 handler 都重播被入口 redirect 覆蓋的原始 prologue。原 MZ relocation 沒有移除或搬動；短入口原有的 relocation 被重新用作遠跳至既有 resident FONT trampoline。

## 真實遊戲驗證

使用 SAVE01：右鍵兩次切到眼睛、移回 `(160,20)`、左鍵點門上方 NPC、按 `1`、按 `Esc`。

- 初始對話：queue 為 active，包含 NPC 行與五個完整英文選項；`surface_id=3`。
- 選擇回覆 1：generation 增加，舊六行被新 NPC 回覆取代。
- Esc：`active=false`，commands 為空。
- 原 320×200 畫面、互動、游標及原文字繪製皆保留。

證據：

- `D:\git\dsun-hires-text-poc\v9\artifacts\dialogue-command-queue.json`
- `dialogue-queue-initial.png`
- `dialogue-queue-response-1.png`
- `dialogue-queue-closed.png`

候選 runtime：`D:\git\dsun-hires-text-poc\v9\runtime-dialogue-queue`

## Queue contract v1

Mailbox signature 為 `POC9DLG1`，採 odd/even sequence 發布，避免讀到半完成資料。每筆固定大小 record 保存 surface、signed x/y、長度及最多 159 bytes 的 NUL 結尾文字。

目前已特別解析遊戲實際使用的 `%C%C%s`，因此 response 選項保存的是完整字串，而不是 formatter template。Base94/CJK transport bytes 原樣保存，交由下一層字型解碼與 Hires 排版。

## 下一步

下一階段可讓 Hires renderer 直接消費這個 queue，先覆蓋 EBox 的 NPC 主文與 response 選項，再把 cursor 合成固定在最後一層：低解析圖形 → Hires Text → cursor → present。
