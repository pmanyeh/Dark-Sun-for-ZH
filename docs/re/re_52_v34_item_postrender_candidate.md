# v34 物品說明 post-render 實驗（實機否決）

> 狀態更正：2026-08-17 實機否決。物品說明視窗只剩介面、沒有文字；連續查看數個物品後遊戲閃退。請勿再以 v34 作為測試基準。

日期：2026-08-17

## 狀態

- 穩定基底：`scratch_test/cjk_display_staging_v33_dense_banks`
- 候選版本：`scratch_test/cjk_display_staging_v34_item_postrender`
- 遊戲內驗證：失敗
- v33 對話與法術說明：使用者已確認正常
- v33 物品右鍵說明：仍為 Base94 亂碼

## 先前失敗原因

v29 的 `%Fs` 實驗在呼叫 FONT 前便將來源指標前移。FONT 除了字形參數之外，仍可能依賴當前的 `ES:BX`／來源狀態，因此造成既有英文與中文 UI 的連鎖破壞。

## v34 修正設計

物品格式化迴圈改為：

1. 以原始 `ES:BX` 呼叫 Base94 解析器。
2. 將 ASCII/CJK 長度旗標保存於格式化器已不再使用的 `[bp-1A]`。
3. 清除 `AH`，確保 FONT 收到 `0x00xx` 字形值。
4. 在來源指標保持不變時呼叫 FONT。
5. FONT 返回後，再依旗標將 `[bp-0E]` 前移 1 或 3 bytes。
6. 載入下一個來源位置並檢查 NUL，繼續或退出原迴圈。

post-render helper 位於常駐段 `36AA:51F1`（格式化器別名 `339E:82B1`）。原版與 v33 的對應 433-byte 區段皆為全零，且沒有 MZ relocation 項。

## 離線驗證

- `%Fs` 主迴圈、far bridge、post-render helper 已逐條反組譯核對。
- 新 FONT far-call 與 bridge far-call 的 MZ relocation 已由工具重寫並驗證。
- `python -m unittest discover -s tests -p 'test_*.py'`：45 tests passed。
- 建置工具預設 `autolock=false`。
- 未對執行中的 v33 做任何即時記憶體修改。

## 存檔

已由 v33 複製以下檔案到 v34：

- `DARKRUN.GFF`
- `CHARSAVE.GFF`
- `SAVE01.SAV`

其中 `DARKRUN.GFF` 與 `SAVE01.SAV` SHA-256：

`17D58458363DA12BEBB4497E77DC373317C77329F325E1FA1BFCFB093C226111`

## 下一步

已恢復 `scratch_test/cjk_display_staging_v33_dense_banks`，存檔雜湊未變。後續須重新追查 `%Fs` 呼叫慣例與 FONT 輸入狀態，不再對 v34 做遊戲內測試。建置工具會拒絕 `--experimental-item-text-fix`，避免誤建已知會閃退的版本。

後續離線候選設計見 `docs/re/re_53_v35_item_stack_candidate.md`；v35 尚未啟動或實機驗證。
