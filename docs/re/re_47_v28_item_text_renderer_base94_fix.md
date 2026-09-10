# v28 物件文字繪製器 Base94 初次嘗試（已由 v29 取代）

> 更正：本文件記錄的 `339E:0205` near-call 修補沒有涵蓋資訊卡的
> `%Fs` 名稱分支，而且 segment alias 會令 resolver 的 `CS:` 資料存取失效。
> 請以 `re_48_v29_item_format_farcall_fix.md` 為準；v28 不應作為測試基準。

日期：2026-08-17

## 結果

已定位物件／角色資訊區使用的逐字繪製迴圈，並讓它重用既有的 Base94 中文解析器。修補後，普通英文與 `%` 格式字串仍走原本流程；遇到 `^..!` 三位碼時，會載入 CJK 字模、只畫一個中文字，並正確略過另外兩個編碼位元組。

## 動態定位證據

- 物件名稱 `長劍` 的執行期字串位址為 `78E7:02C0`，內容是 `5E 29 43 5E 21 7C 00`。
- 物件文字包裝函式為 `2143:0A40`，其底層逐字繪製函式為 `339E:016D`。
- 原始逐字取值點在 `339E:0205`：`mov al,es:[bx]`，之後呼叫 `11A4:59C1`。
- 既有 `36AA:53E6` 包裝器正好使用同一個 `[bp-0A]` 字串游標，會呼叫 `36AA:5420` Base94 resolver，中文字時額外推進兩個位元組。
- `339E` 與 `36AA` 是同一載入映像的不同 segment:offset 表示法；`36AA:53E6` 可等價表示為 `339E:84A6`。

## 修補方式

把 DSUN.EXE 檔案位移 `0x30DA5` 的：

```text
26 8A 07 98    mov al,es:[bx] / cbw
```

替換成：

```text
E8 9E 82 90    call 339E:84A6 / nop
```

這是近距離呼叫，不新增 MZ relocation；後方既有的 `push ax` 與 `call 11A4:59C1` 完全保留。

## 實作與驗證

- 實作：`tools/patch_dsun_scratch_cache.py`
- 建置 manifest 標記：`tools/build_cjk_display_staging.py`
- 測試：`tests/test_cjk_localization_pipeline.py`
- 全部 44 個單元測試通過。
- `git diff --check` 只回報既存 localization catalog 的尾端空白，這次三個程式／測試檔沒有新增 whitespace 錯誤。
- v28 隔離測試版：`scratch_test/cjk_display_staging_v28_item_text_fix`
- v28 DSUN.EXE SHA-256：`8975dc99da985cdaa2400ed6a6b0777039b92fcb12a6bfc082882a5333355c2c`
- v28 檔案位移 `0x30DA5` 已驗證為 `E8 9E 82 90`，manifest hash 與實檔一致。

## 測試環境狀態

- 目前執行中的 v27 已套用相同的記憶體熱修補，方便直接人工確認。
- 所有 debugger breakpoint 已清除。
- execution trace 已關閉。
- 所有注入輸入已釋放。
- Steam 原始遊戲目錄沒有被修改；v28 僅建立在 `scratch_test` 隔離目錄。

## 尚待人工確認

目前游標位置開出的資訊卡實際顯示 `Bone`、價格與戰鬥屬性，畫面本身沒有顯示物件名稱列。核心 Base94 路徑已完成動態命中與熱修補驗證，但仍需在會實際顯示 `長劍` 名稱的 UI 狀態下做最後截圖確認。
