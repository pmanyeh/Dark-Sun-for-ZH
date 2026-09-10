# v35 物品說明堆疊保存實驗（實機否決）

> 狀態更正：2026-08-17 實機否決。載入遊戲後客體 CPU 與模擬時間仍持續前進，但畫面完全不再更新，遊戲陷入非中斷式卡死。請勿再次啟動 v35。

日期：2026-08-17

## 狀態

- 穩定執行版：`scratch_test/cjk_display_staging_v33_dense_banks`
- 離線候選版：`scratch_test/cjk_display_staging_v35_item_stack_candidate`
- v35 遊戲內驗證：失敗，非中斷式卡死
- v34：實機否決，建置工具會拒絕舊選項

## v34 失敗後確認的風險

v34 的 post-render helper 使用 `add byte [bp-0E],al` 前移 `%Fs` far-string offset。這只修改低 8 bits；例如 ASCII 的 `00FF + 1` 會錯誤變成 `0000`，而不是 `0100`。連續查看物品後，錯誤指標足以導致讀取錯誤位置與閃退。

v34 也把解析器回傳的 ASCII/CJK 長度旗標寫入格式化器的 `[bp-1A]` 區域變數。雖然靜態控制流程中該欄位看似已完成分派用途，實機出現「只剩介面、沒有文字」，因此 v35 不再使用任何外層區域變數保存旗標。

以上能確認 v34 至少包含指標進位錯誤；無文字症狀是否完全由區域變數覆寫造成，尚未宣稱定論。

## v35 指令流程

1. far call `36AA:5414`，resolver 以 `AX=00xx` 回傳 ASCII，或以 `AX=017F` 回傳 CJK marker 與三位元組旗標。
2. `push ax` 保存完整 resolver 結果。
3. `xor ah,ah`，再 `push ax`，使 FONT 只收到乾淨的 16-bit 字形值。
4. far call FONT `11A4:59C1`；來源 `ES:BX` 仍指向當前字元。
5. 丟棄 FONT argument，從堆疊恢復原始 AX。
6. post-render helper 將 AH 轉成長度 1／3，以 `add word [bp-0E],ax` 前移完整 16-bit offset。
7. 載入下一個 `ES:BX`、檢查 NUL，迴圈或回到原格式化器。

堆疊在每個字元迭代前後完全平衡。v35 不使用 v34 的 `[bp-1A]` 暫存。

## 離線驗證

- 指令契約測試涵蓋 resolver/FONT 之間的 push/pop 順序與分支目標。
- ASCII：來源前移 1 byte。
- CJK：來源前移 3 bytes。
- carry 邊界：`00FF + 1 = 0100`、`00FE + 3 = 0101`。
- `%Fs` 主迴圈、post-render helper、far wrapper 已以 16-bit objdump 逐條核對。
- MZ relocation：新增 `0x30E8E`、`0x30E97`，移除原 `0x30E93`。
- v35 與 v33 的 MZ load image 只有三個預定程式區塊不同。
- `RESOURCE.GFF`、`GPLDATA.GFF`、`C0`～`C5` 與 v33 完全相同。
- `autolock=false`。
- 完整測試：46 tests passed。

## 啟動前防呆與安全觀測

新增 `tools/verify_cjk_item_candidate.py`。它在啟動前 fail closed 檢查：

- manifest 必須明確標記 `candidate=true`、`runtime_status=not_run`；
- 必須存在 `CANDIDATE-NOT-VALIDATED.txt`；
- item profile、三個機器碼區、MZ relocation 與 EXE hash；
- `autolock=false`；
- RESOURCE、GPLDATA、C0～C5 與 manifest／v33 baseline 一致；
- load image 差異只能落在三個核准區段；
- DARKRUN、CHARSAVE、SAVE01 存在，且 DARKRUN／SAVE01 相同。

v35 preflight 已通過；v34 因缺少候選標記而被拒絕。未來由 builder 產生的 v35 也會自動寫入上述 manifest 欄位與警告檔。

v33 以具有真實 Win32 console 的流程重新啟動後，DOSBox-X AI bridge 已在 `127.0.0.1:9876` 正常監聽。純讀取測試依序呼叫 debug status、mouse capture status 與 framebuffer capture：

- 呼叫前後皆為 `running=true`；
- `captured=false`、`autolock=false`、mouse mode `absolute`；
- 客體畫面為 640×400；
- 沒有送出任何鍵盤或滑鼠事件，也沒有暫停 CPU。

因此後續候選實測可使用 framebuffer capture 觀測，而不必用 OS 桌面自動化或 RAM hotpatch。

## 雜湊

- v35 `DSUN.EXE`：`52E1D5F8C37F6474786EBF0FF026CF20AC14BA775174F939DEB574FF1548941F`
- `DARKRUN.GFF`／`SAVE01.SAV`：`17D58458363DA12BEBB4497E77DC373317C77329F325E1FA1BFCFB093C226111`
- `CHARSAVE.GFF`：`54ABB1C48EDBA31982E56C10AB893735EBEA9B320CE4628DFA4C9BB2465D3F60`

## 實機否決證據

載入後遊戲停在戰鬥畫面且不再更新，但並未進入 Debugger：

- 兩次 `get_debug_status` 均為 `stopped=false`、`running=true`；
- 兩次 frame capture 的 frame ID 由 2 增至 3；
- emulated time 由 150441 增至 150854 ms；
- 兩張 PNG 內容完全相同；
- host 程序仍有 CPU 活動且視窗 `Responding=true`。

因此分類為客體遊戲主迴圈卡死，而不是 DOSBox-X 中斷或 Windows 視窗無回應。v35 的執行中 `DARKRUN.GFF` 為 11011 bytes，SHA-256 `D33AAD24638EECD0C918DA4EC9BCDC7C4663204A953BCC787842BC93FDAAE5CA`；它未覆蓋正式存檔，只保留為鑑識備份。

## 下一步

v35 已禁止再次啟動，builder 也會拒絕 `--experimental-item-text-fix-v35`。已恢復 v33；正式 `SAVE01.SAV` 未遭覆蓋。v35 執行中的 11011-byte `DARKRUN.GFF` 另存為 `DARKRUN.v35-hang-backup.GFF`，只供離線鑑識。

後續不得再沿用「整段重寫 `%Fs` 迴圈」的 v29／v34／v35 路線。下一輪應先比較穩定 v33 與原版在物品 tooltip／右鍵資訊卡的完整呼叫鏈，找出更上游且可局部替換的文字來源或 renderer dispatch；在確認前不建立下一個實機候選。

## 後續新增的 I/O thrashing 假說（尚未單獨實機證實）

`re_54` 已證明物品畫面會高頻重繪同一個 NAME：長劍至少出現在底部 hover、
右側資訊與右鍵說明卡。v35 對每個 Base94 triple 都呼叫現有的單格 scratch loader；
該 loader 每次 miss 會執行 CJB1 open、directory seek/read、glyph seek/read、close，並
覆寫唯一的 FONT marker `0x7F` record。

「長」與「劍」交替顯示時，單格 cache 必然每字 miss；三個 UI consumer 反覆重繪時，
可能形成大量同步 DOS file I/O。這與 v35 的「guest CPU／emulated time 前進，但畫面
內容不更新」高度相符。因此 v35 的 hang 不宜只歸因於 stack ABI；I/O thrashing 是
目前更具體的新嫌疑，但尚未用 DOS I/O event log 對 v35 單獨重跑驗證，而且 v35 已
禁止啟動，故不為此假說重開否決版本。

v33／v35 dense-bank profile 的實際 scratch record 是 102 bytes（不是舊 16×15
實驗的 242 bytes）。安全的新方向是多格 glyph cache／名稱級預解碼，使同一個最多 7 字的 NAME 在首次
載入後重繪只命中 RAM，不再每一幀反覆開檔。此方向必須另建離線設計，不能解除
v35 的拒絕狀態。
