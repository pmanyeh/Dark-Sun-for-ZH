# v29 物件資訊卡 `%Fs` Base94 far-call 修補

> 狀態更正（2026-08-17）：v29 的執行檔修補有效，但可玩 staging 誤用了非累積的
> `gpl6_balkazar_zh_v1`，導致 GPL2～5、GPLI 與 NAME 中文未納入。請勿再以 v29
> 作為翻譯測試版；已由累積封包重建的 v30 取代。

日期：2026-08-17

## 問題更正

畫面中 `Bone` 下方的 `V)CV...` 亂碼是 `長劍` 的 Base94 bytes 被逐個送進 FONT renderer。動態 breakpoint 證實真正呼叫點是 `339E:02F0`，位於 `%Fs` 遠端字串分支；先前修補的普通字元分支 `339E:0205` 只處理 `PSI:` 等其他 UI 文字。

near-call 到 `36AA` 的 physical alias 也不正確：指令雖相同，CS 仍是 `339E`，resolver/cache 的 `CS:` 檔名表因此讀錯並回傳 `AX=013F`。正確入口必須是 relocated far call，使 CS 真正切換到 `36AA`。

## v29 實作

- 重寫 `339E:02EB..0305` 的 `%Fs` 逐字迴圈。
- far call `36AA:5414` 解析普通 byte 或 Base94 triple。
- wrapper 將 resolver 的 AH=0/1 轉成來源游標前進 1/3 bytes，再清除 AH。
- far call 原 FONT renderer `11A4:59C1`。
- wrapper 主體 12 bytes 位於六個 CJB1 bank 檔名表結尾 `36AA:5414`。
- 最後 `xor ah,ah / retf` 3 bytes 位於高度 helper 後方安全空隙 `36AA:53E1`。
- MZ relocation 從原 segment word `0x30E93` 移除，新增 `0x30E8E` 與 `0x30E94`；load image 不搬動。
- EXE header relocation table 尚有 2030 bytes 空間，新增一筆後仍有充足餘裕。

## 驗證狀態

- 21 項 CJK pipeline 測試通過，包括 relocation 集合驗證。
- v29 成功建置並能正常啟動至主選單。
- v29 隔離目錄：`scratch_test/cjk_display_staging_v29_item_format_farcall_fix`
- DSUN.EXE SHA-256：`25c8710e4a484b8d26e581f1e0f4a0f30f9c5acab8813049d6cc9a6c3bfd3673`
- Steam 原始遊戲目錄未修改。

## 待確認

需由主選單載入原存檔，再對長劍按右鍵，完成最終畫面確認。DOSBox-X 絕對座標在目前 normal2x 畫面仍有校準偏差，因此暫停自動點選，交由人工操作避免誤選。
