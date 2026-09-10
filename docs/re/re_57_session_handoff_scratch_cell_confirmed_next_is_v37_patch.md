# Session 交接：暫存格候選已確認，下一步是實作 v37 patch

> 日期：2026-08-18
> 前置文件：`re_55_fbov_overlay_relocation_and_ds_relative_redirect_design.md`、
> `re_56_dgroup_tail_candidate_disproven_by_dynamic_watchpoint.md`

## 1. 本輪做了什麼

延續 `re_55` §7 排定的工作：連上 DOSBox-X-AI，用動態監看驗證 DGROUP 尾端候選
暫存格是否真的安全。完整過程與證據記在 `re_56`；本文件只做交接摘要，細節一律
以 `re_56` 為準。

### 1.1 環境確認

- DOSBox-X-AI MCP server 在新對話裡可正常抓到（deferred tools 重新載入即可用）。
- 但 MCP server 在線不代表 DOSBox-X 進程有在跑，兩者要分開確認
  （`ping`／`get_project_status` 只測 server；`get_debug_status` 才測真正的模擬器）。
- 啟動指令固定用
  `scratch_test/cjk_display_staging_v26_gpli_event_relocation_gap2/launch-dosbox-x.cmd`。
  **不要用 Bash 的 `cmd /c` 呼叫它**——MSYS/git-bash 會把 `/c` 誤判成路徑轉換，
  導致只開一個空白 cmd 視窗、什麼都沒執行就關掉。改用 PowerShell
  `Start-Process -FilePath <cmd 檔> -WorkingDirectory <staging 目錄>`（非阻塞）才會
  真的啟動。

### 1.2 re_55 §7 候選假設被推翻

`re_55` 用磁碟靜態零掃描找到的最大候選區（`DS:0x427A` 起 25154 bytes）被證實
**不是空地**：至少 `0x427A`（高頻遠指標組裝寫入）與 `0x8A7A`（場景轉換 `rep
stosw` 批次填充 `0xFFFF`）兩處是實機證實的熱點。純靜態零掃描不可靠，已改用
「執行期完整記憶體快照比對」取代（`re_56` §6-7）。

### 1.3 新候選已確認：`DS:0x6100`

用 `D:\git\DOSBox-X-AI\ai\dosbox_client.py` 直接寫小腳本做快照 dump／逐 byte
比對（繞開把 25000+ bytes 塞進對話上下文會爆輸出限制的問題，腳本存於
`C:\Users\pmany\AppData\Local\Temp\claude\d--git-Dark-Sun-Series\09b555a3-e99b-467a-8873-1c4f8b8c5dd3\scratchpad\dgroup_snapshot.py`，
是本次 session 的暫存檔案，不在專案 repo 內，下次要重跑同樣方法得重寫或另存到
`tools/`）。

找到 `DS:0x5AB4` 起連續 3036 bytes、兩次快照都全零的大區間，取正中央
`DS:0x6100` 當最終候選，再用精準監看點對這 4 bytes 做主動監看，涵蓋戰鬥、法術、
地圖、多選項對話後仍未觸發。**三輪獨立證據交叉確認，目前是最佳候選，但仍是
動態抽樣、不是數學證明。**

### 1.4 順便解決的兩個插曲（跟主線任務無關，但值得記住）

1. **存檔後閃退**：使用者遊玩中觸發了一次。查證後確認是
   `vendor/opends/docs/known-bugs.md` §2.4「Saves but exits」的已知 pre-existing
   engine 問題（存檔本身有成功寫入，只是遊戲跟著關掉），**跟本次監看點操作無關**。
   已把「遇到異常先查 known-bugs.md／engine-quirks.md，不要先假設是本次工具造成」
   這個教訓存進 agent 記憶。
2. **物品名稱三處畫面 ↔ 四個 consumer 的對應關係**，已用截圖跟 `re_54` 逐一核對
   確認：

   | 畫面位置 | consumer file offset |
   |---|---|
   | 底部滑鼠懸停名稱列 | `0x06E288` |
   | 右鍵物件說明卡 | `0x072955` |
   | 右側裝備／攻擊資訊欄（兩種條件分支） | `0x08BECF`、`0x08BF00` |

## 2. 目前狀態

- DOSBox-X 目前仍在跑（v26 checkpoint，`scratch_test/
  cjk_display_staging_v26_gpli_event_relocation_gap2`），沒有掛任何 breakpoint，
  乾淨可繼續遊玩或直接關閉。
- **沒有修改任何 build**、沒有寫入 guest RAM、沒有新增或變更任何已存在的
  staging 版本。`DSUN.EXE`／`GPLDATA.GFF` 均未被 patch。
- 存檔進度在 `SAVE08.SAV`（`scratch_test/
  cjk_display_staging_v26_gpli_event_relocation_gap2/GAME/DARKSUN/`）。

## 3. 下一步（明天接續）

實作 `re_55` §6 設計的 v37 patch：

1. 把已組譯好的 391-byte 解碼器核心（`tools/cjk_name_slot_cache.asm`，位於
   `36AA:51F1..5377`，`re_54` 最後一節已驗證大小與位置）跟本輪確認的暫存格
   `DS:0x6100` 接起來——`re_55` §6 的 14-byte 呼叫端序列（`mov bx,ds` /
   `sub bx,0x14D0` / `mov [mem_seg],bx` / `call far [mem_off]`）裡的
   `mem_seg`／`mem_off` 要改指到這個新位址。
2. 對 `re_54` 已定位的 4 個 consumer call site（`0x06E288`、`0x072955`、
   `0x08BECF`、`0x08BF00`）套用等長替換，取代它們原本組 far pointer 的 14-byte
   序列。
3. 建置新 staging（下一版本號是 v37），沿用既有 `NAME_objects_translated.json`
   翻譯資料與 `cjk_mapping.json`。
4. 建版前跑相關 unit tests；建版後**三個畫面位置分別驗證**（底部懸停、右鍵
   說明卡、右側欄位兩種分支都要各測一次），並回歸 v26 既有的囚犯／出口／
   競技場／對話行距。
5. 若 v37 在某個 consumer 上仍失敗，優先懷疑暫存格選址（`DS:0x6100`）或
   `DS-0x14D0` 差值公式的邊界情況，而不是重新懷疑 FBOV 格式或 v36 根因分析
   ——那兩塊已經多輪驗證過，不必重做。
