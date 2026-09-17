# v56：固定 BACKPACK 文字的中文顯示候選版

> 日期：2026-09-10
>
> 狀態：使用者已提供 v56 截圖，確認底部「背包」正常顯示、置中並落在框內。
> 使用者已驗收的 v55 保持不變。這次只處理「BACKPACK → 背包」，不是整套固定 UI 翻譯。

使用者的這次回報驗證了單列固定文字顯示；角色切換、所有 hover／右鍵組合與長時間
重繪仍不能僅憑一張截圖視為全部通過。以下 `not_run` 為當時建置 metadata，保留原始紀錄。

## 1. 啟動與驗收

啟動檔：

```text
scratch_test/cjk_display_staging_v56_backpack_ui/launch-dosbox-x.cmd
```

關閉舊版遊戲後，雙擊上述檔案，或從專案根目錄的 PowerShell 執行：

```powershell
& '.\scratch_test\cjk_display_staging_v56_backpack_ui\launch-dosbox-x.cmd'
```

請檢查：

1. Load Game 後能正常打開物品介面。
2. 游標移到原本會顯示 BACKPACK 的**空背包格**，底部名稱列顯示「背包」。
   放有物品的格子應繼續顯示物品名稱，不是「背包」。
3. 在空格、中文物品、英文物品間來回移動，文字應正確切換、置中，不留殘影。
4. 切換角色、開關物品欄、右鍵物品說明，再返回空格，確認沒有亂碼或當機。
5. K’Ratchek 的右側七列仍維持 v55，不應再次超出底框。

這個版本沿用底部名稱列的單列呈現方式，不增加新的一行，也沒有動右側能力或武器區。
實際中文字下緣、水平置中及清除範圍仍須以上述實機步驟確認。

## 2. 局部接入方式

v55 的物品 NAME 解碼核心，只接受 AX 中的 NAME ID。v56 增加可選的固定背包入口，
未啟用選項時，組譯輸出仍逐 byte 重現 v55 的 653-byte 核心。

本次 EXE 僅替換 `0x6E111..0x6E11F` 共 15 bytes：

```text
原本：建立 BP frame，將文字 far pointer、2C06 及 DS:11A4 的 far pointer 入棧
現在：使用既有 DS-relative / FONT-local trampoline，返回 overlay IP 23A0
返回位置：0x6E120 原本的 far renderer call，保留不變
```

新增的 FONT-local dispatch 檢查 synthetic return IP `23A0`，只將新入口轉送到 adapter。
既有四處 NAME caller 的 continuation 是 `2516 / 2B93 / 0FFD / 102E`，仍走 NAME 路徑。
此判別只適用於雜湊鎖定的 v55；不能把補丁套用到任意 EXE。

Adapter 僅在原始文字 far pointer **同時**符合 offset `1853h` 與 segment `DS` 時翻譯。
其他文字（包含相同 offset、不同 segment）維持原指標。它重建原函式的 BP frame、
10 bytes 繪圖參數及返回位置，然後交還原本的 renderer。

「背包」使用既有 mapping 的 CJK IDs `1303 / 100`，建置時確認 v55 的 C5 / C0 中
確實存在各 102 bytes 的 10×10 字形。本次不改 mapping、banks 或 NAME-1。

固定背包使用快取 key `FFFEh`，避免與正常 NAME ID 混淆。解碼後仍是既有可列印
slot `22h / 23h`，FONT 中字形寬度各 10px；因此原 renderer 收到兩個字形碼，而不是
六個未解碼的 Base94 bytes。這不等同於已驗證畫面上的置中或裁切結果。

切換到其他 NAME ID 會重載物品字形；再回背包也會重載背包字形。連續 hover 背包則
命中快取，不重複讀檔。這個版本沒有額外建立永久占用的固定 UI 字形槽。

## 3. 建置與驗證

建置指令（輸出目錄必須不存在）：

```powershell
python tools/build_backpack_ui_candidate.py
```

可用 `--source` 和 `--output` 指定位置。建置器先鎖定 v55 EXE、RESOURCE、FONT 雜湊，
只在新的暫存目錄製作並驗證，完成後才移到候選版位置；拒絕覆寫既有候選目錄。

結果：

- EXE 只有上述 15-byte 範圍不同，其餘 bytes 相同，MZ relocation table 沒有變動。
- 所有右側座標、行距、global-height helper 及既有 resident trampoline 不變。
- FONT 原本的 header、字形、動態槽區完全相同；FONT-local core 從 653 增至 745 bytes。
- GFF 抽取驗證：1205 chunks；只更換 FONT-100，1203 個非目標內容不變，
  另允許容器 metadata GFFI-1 隨重建變動。
- 73 個其他來源檔案複製內容一致，包括 banks、存檔、launcher、設定；保留 `autolock=false`。
- 最後再次核對 v55 EXE / RESOURCE 雜湊未改變。
- 84 個測試通過，其中 4 個為 Unicorn 16-bit 執行測試，沒有 skip。

模擬測試執行實際組譯出的 redirect、trampoline、adapter、NAME core 及 glyph loader，
DOS 檔案中斷以合成 CJB1 資料模擬，確認：

- 中文與非中文分支都回到原 overlay continuation；棧位置、BP、DS/ES、SI/DI 正確。
- 原繪圖參數保留，背包輸出兩個 slot；各 slot 具有正確的 10×10 字形資料。
- 背包重複命中快取；背包 → 中文 NAME → 背包會正確換字形；ASCII NAME 仍通過。
- 非 BACKPACK 指標及同 offset 不同 segment 不會誤翻譯。

Unicorn 僅裝在忽略的 `scratch_test/ui_emulation_deps`，沒有更動專案套件環境。
重跑全部測試（含模擬）：

```powershell
$env:PYTHONPATH = (Resolve-Path scratch_test/ui_emulation_deps).Path
python -m unittest discover -s tests
```

沒有 Unicorn 時，4 個模擬測試會明確 skip。模擬在原 renderer 呼叫前停止，
**不涵蓋 DOSBox Load、實際像素繪製、置中、裁切或重繪殘影**，不能視為實機通過。

## 4. 候選版雜湊與 metadata

```text
DSUN.EXE
e972af58edc0936fe7510cd442a9b67a5747d3f73aa78ea6ea45386d780e91a2

RESOURCE.GFF
8d924107807992a1c711e52c0d5fd6989db3ede698b06fe2762f926b0a5a71de

FONT-100 (9860 bytes)
883bf40550c4113f98cf900e7eb12df8cf636e959ad4ca2f89124ed9896d2aaf
```

本版以 `build-backpack-ui-manifest.json` 為準，runtime_status 仍為 `not_run`。
目錄內繼承的 `build-manifest.json`、`build-name-slot-manifest.json` 描述祖先版本，
不是本次輸出的雜湊；另有 `V56-READ-ME.txt` 說明。

待這個單列探針實機通過後，再擴展能力標籤的儲存區、中文字庫與雙路徑 10px 對齊。
