# docs/re/07-verified-gpl-loop-and-dosbox-setup.md
# 已驗證進度：GPL 執行迴圈反組譯 + 可運作的 DOSBox 除錯環境

> **日期**：2026-08-10
> **重要提醒**：`re_01` ~ `re_06` 裡許多「已完全破譯」的結論**未經驗證、部分為誤判**（例如 `re_05` 宣稱定位到 `0x001720` 的解碼迴圈，實際上該位址落在 MZ 檔頭範圍內，根本不是程式碼）。本篇取代前幾篇文件中所有具體位址與演算法的說法，只記錄**真正用 Ghidra 反組譯/反編譯驗證過**、或**用真實截圖驗證過**的內容。

---

## 1. 已驗證的技術事實

### 1.1 DSUN.EXE 是分兩塊的：常駐段 + Overlay 池
* `DSUN.EXE` 檔案大小 611408 bytes，標準 MZ real-mode 執行檔，MZ loader 只會載入到檔案偏移 `0x52ea0` 為止（常駐段，約 317KB）。
* **檔案偏移 `0x52ea0` 到檔尾**（約 271KB, `0x425b0` bytes）是 **Borland/Turbo C++ Overlay Linker** 的 overlay 池：
  * 常駐段內有 **994 個 `CD 3F`（`int 3Fh`）** 呼叫樁，是 Borland overlay manager 的標準特徵。
  * overlay 池內找到 947 個 `55 8B EC`（`push bp; mov bp,sp`）函式開頭，證實是真正編譯過的程式碼，不是資料。
  * overlay 的跳轉/分派表在**磁碟檔案裡的內容是全 0**，要等 overlay manager 在執行期把程式碼讀進記憶體時才會被動態填值 → **純靜態分析在這裡會卡住，需要動態除錯或 IDA/Ghidra 對執行期記憶體 dump 才能解開**。

### 1.2 真正的 GPL 記錄執行迴圈（已用 Ghidra 反組譯驗證）
* 函式位於 overlay 池內，**檔案絕對偏移約 `0x68000`**（Ghidra 內部標記為 `FUN_0000_5160`，之前錯誤地寫在 `tools/decompile_ssi_text_decoder.py` 猜測的位址完全不對）。
* 記錄格式（100% 從反組譯碼讀出來，不是猜的）：
  ```
  offset 0    : 1 byte  opcode
  offset 1-7  : 未解析欄位
  offset 8-9  : 2 bytes 長度欄位
  offset 10   : 長度可變的內容 (長度 = offset 8-9 的值)
  ```
  * 若 `opcode` 屬於 `1~4`：透過 `CS:0x38F` 處的跳轉表分派到特殊處理函式（**此表在磁碟上是全 0，需執行期才知道真正位址**）。
  * 其他 opcode：指標前進 `10 + 長度欄位值`，直到遇到 `0xFF` 結尾。
* 錯誤處理路徑對應驗證：
  * `FUN_0000_5234(0x1a8, 0x13f5)` = 呼叫「gpldisk out of memory」錯誤訊息（位址精確對上）。
  * `FUN_0000_8cb7` 呼叫 `FUN_0000_4d2a(0x163e)` = 「BAD GPL EXIT」錯誤訊息。
  * 這些字串（`gpldisk out of memory`、`Bad iCtrl in gpldisk.c`、`FATAL: Error allocating NARRATE text` 等）**是編譯器留下的真實除錯字串**，證實原始碼檔名確實叫 `gpldisk.c`。

### 1.3 專有名詞是純文字，完整句子不是
* `Gerakis`（NPC 角色名）以 null-terminated 純 ASCII 字串存在 `SEGOBJEX.GFF`（檔案偏移 `0x3863ab`），跟同檔案裡的 `Fire Eel`、`Drajian Guard` 是同一種「生物/角色物件資料記錄」結構。
* 但完整句子（例如下面驗證到的對話）**在任何遊戲檔案的任何簡單編碼變換下都找不到**，證實敘事文字確實是**執行期動態組出來的**，不是靜態壓縮字串——這點跟舊文件的猜測方向一致，但舊文件從未真正解出組句演算法。

### 1.4 已用截圖驗證的真實遊戲對話（不是猜的、不是 AI 生成的）
開場鬥技場橋段：
> "This day the mage Celgor will battle a fearsome rampager. Watch and enjoy!"
> "Do not worry, Gerakis. Your turn will come soon. Stand back and watch the battle."

截圖檔：`D:\ghidra_re\dosbox\captures\dsun_000.png`

---

## 2. 可重複使用的環境與工具

### 2.1 Ghidra（已裝好，可重複使用）
* 安裝路徑：`D:\ghidra_re\ghidra`（注意：路徑刻意選在**無空白字元**的地方，因為 `analyzeHeadless.bat` 對含空白路徑的參數解析在這個環境下不穩定）。
* 專案：`D:\ghidra_re\project\DarkSunRE`（完整 `DSUN.EXE` 常駐段，已跑過自動分析）。
* 額外匯入的 overlay 切片（供交叉比對）：`OverlayChunk1`（對應 tail `0x10000-0x20000`，含 `gpldisk.c` 相關函式）、`OverlayChunk2`（tail `0x20000-0x30000`，含 `NARRATE` 配置錯誤處理）。
* 自訂 Ghidra 腳本都存在 `D:\ghidra_re\scripts\*.java`，用 `analyzeHeadless.bat <proj> <name> -process <file> -noanalysis -scriptPath D:\ghidra_re\scripts -postScript <Script>.java` 執行。
* **注意**：`analyzeHeadless` **沒有 `-analyze` 這個參數**！匯入時預設就會自動分析，硬加 `-analyze` 會被誤判成檔案路徑而報錯。

### 2.2 DOSBox-X + 遊戲能正常開機的關鍵設定（已驗證可行）
* DOSBox-X 安裝於 `D:\ghidra_re\dosbox`，設定檔 `D:\ghidra_re\dosbox\darksun.conf`。
* **關鍵**：一開始亂猜的 `cycles=auto` 或隨便設的 `cycles=3000` 都會讓遊戲一開機就靜默當掉（連錯誤訊息都不印，因為遊戲的錯誤訊息是直接寫顯示記憶體，不是標準輸出，重導向沒有用）。
* **真正能動的設定，是直接抄 Steam 版內建launcher 的原廠設定**（在 `from Steam\games\Dark Sun-ENG\base.conf` / `game.conf` / `graphics.conf`，Steam 版其實內建了一份 DOSBox 0.74-3 + 這三個設定檔，啟動指令是 `DOSBox.exe -noconsole -conf base.conf -conf graphics.conf -conf game.conf`）：
  * 最關鍵的一項：**`cycles=fixed 7000`**（不是 auto）。
  * 明確指定音效卡：`sbtype=sb16, sbbase=220, irq=5, dma=1, hdma=5`。
  * `machine=svga_s3`, `memsize=32`。
* 啟動遊戲要用 `DARKSUN.BAT`（會先做音效卡偵測），直接執行 `DSUN.EXE` 會啟動失敗。
* 除錯器截圖熱鍵：**`F11 + P`**（不是預設文件說的 Ctrl+F5），存到 `[dosbox] captures=` 指定的資料夾（目前設定為 `D:\ghidra_re\dosbox\captures`）。
* 除錯器常用指令備忘：
  * `BPINT 21 3D` — 中斷於開檔案（DOS INT 21h AH=3Dh）；檔名在 `DS:DX` 指向的記憶體，用 `D <DS值>:<DX值>` 檢視。
  * `BPM <seg>:<off>` — 記憶體寫入變化中斷點（可用來抓 VGA 顯示記憶體 `A000:0000` 的寫入，藉此抓到繪圖/文字渲染程式碼，但要注意背景圖/頭像等無關畫面也會觸發，需要多按幾次 F5 篩選）。
  * `MEMDUMPBIN <seg>:<off> <len>` — 把記憶體存成 `MEMDUMP.BIN`，**檔案會寫在啟動 `dosbox-x.exe` 時的工作目錄**（例如 `D:\ghidra_re\dosbox\bin\x64\Release SDL2\MEMDUMP.BIN`），不是遊戲的模擬 C 槽路徑。
  * `LOG` / `LOGS` / `LOGL` / `LOGC` 家族指令在這個環境下**目前試過都會「Logfile couldn't be created」失敗**，原因未查出，暫時避開不用。
  * 進入除錯器：命令列加 `-break-start`；執行中要強制中斷回除錯器，用視窗選單列的 **Debug > Enter Debugger**（比按 Pause 鍵可靠，Pause 鍵中斷的位置常常是隨機的系統中斷處理常式，不是遊戲程式碼）。

---

## 3. 下一步建議（按優先度）

1. **鎖定 GPL 資料真正被讀取的那一刻**：目前用 VGA 顯示記憶體寫入 (`BPM A000:0000`) 中斷會先撞到背景圖/頭像等無關畫面。更精準的做法是改成 `BPINT 21 3D` 並在中斷後檢查檔名，專門篩選出開啟 `GPLDATA.GFF`（而不是 `DSUN.EXE` 自我重開）的那一次，從那個時間點附近往下找 overlay 分派表的真實位址。
2. 一旦拿到 overlay 跳轉表（`CS:0x38F`）在執行期的真實 4 個位址，回頭用 Ghidra 對「真實載入位址」重新定位、反編譯，應該就能看到組句/繪字的完整邏輯。
3. 名稱類（NAME/SPIN）的純文字抽取與翻譯回寫，是相對獨立、風險低、可以現在就先做出成果的一條支線，跟句子動態組合的難題互不影響。
