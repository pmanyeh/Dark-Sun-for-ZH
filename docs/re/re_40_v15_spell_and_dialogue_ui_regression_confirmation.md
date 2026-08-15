# v15 法術說明與 Celgor 對話 UI 回歸確認

> 日期：2026-08-15
> 延續：`re_39_independent_10row_cjk_draw_and_v15_preferred_checkpoint.md`

## 目標

依 `HANDOFF_NEXT_SESSION_2026-08-15.md` 第 12 節優先順序，回歸確認 v15
（`scratch_test/cjk_display_staging_v15_preferred_complete_text`）在法術說明
彈窗（非 EBOX line-gap context）與 Celgor 開場對話（EBOX line-gap／分頁
context）兩處是否都能正確顯示 10-row CJK，且不與既有 UI 回饋機制衝突。

## 1. 法術說明彈窗

實機開啟法師法術選單，右鍵叫出 GREASE（油滑術）說明彈窗。結果：

- 「油滑術：」標題獨立一行，與 SPIN importer 插入的格式性換行一致；
- 說明本文三行完整顯示，字形下緣與右下陰影皆無裁切；
- 無文字重疊，無亂碼，未閃退。

此路徑與 EBOX 對話框的 line-table／pagination 邏輯是不同的繪製路徑，因此單獨
驗證 10-row CJK draw（`36AA:53D6` height helper、102-byte record）在這條路徑
上是安全的。

## 2. 物品說明與主選單圖示

實機檢視物品欄位說明彈窗（如 `Obsidian Chatkcha`、`Leather Sling`）與
LOAD/SAVE GAME 主選單，確認兩者目前皆為純英文，尚未納入正式翻譯範圍。這與
`HANDOFF_NEXT_SESSION_2026-08-15.md` 第 8 節記載的翻譯覆蓋範圍一致（僅
172 筆 SPIN 法術文字與 4 筆 Celgor GPL 開場對話），不構成顯示層 regression，
純屬待後續擴大翻譯覆蓋的內容缺口。

## 3. Celgor 開場對話（重啟驗證）

為確認 EBOX line-gap 2px／pagination 修正（`re_38`）與 10-row CJK draw
（`re_39`）在 v15 這個確切組合下仍相容，重啟 DOSBox-X 並重新觸發競技場開場。
實機畫面確認：

```text
今日法師賽爾戈將迎戰一頭兇猛的狂暴獸。敬請觀賞！

別擔心，Gerakis。很快就輪到你了。退後觀看這場戰鬥吧。
```

- 文字完整無裁切；
- `MORE` 提示（紅字＋向下箭頭）正常顯示於對話框右側；
- 動態姓名 `Gerakis` 正確插入原 GPL `COMPLEX(... POV ...)` 表達式位置；
- 分頁與捲動未見異常。

## 結論

v15 在目前唯一具備正式中文內容的兩個 in-game 路徑（法術說明彈窗、Celgor
GPL 開場對話）均通過實機回歸確認，且行為與各自前置 checkpoint
（`re_39` 的法術/UI context、`re_38`／`re_37` 的 EBOX 分頁與 GPL 對話）一致。
物品說明與主選單圖示目前無中文內容可測，待後續翻譯覆蓋擴大後應再補測。

v15 可維持為目前最佳可玩 checkpoint；`MORE` hover／按壓變色仍列為 polish
待辦（追 `re_39` 提及的共享 `0x007F` clip-height query），不影響本次回歸結論。
