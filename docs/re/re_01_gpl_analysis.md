# docs/re/01-gpl-interpreter-initial-analysis.md
# DSUN.EXE 靜態分析：第一份逆向筆記

> **輸入**：`DSUN.EXE`（611,408 bytes，MD5 待補）  
> **工具**：Python 靜態字串分析  
> **日期**：2026-08-10  
> **狀態**：初步靜態分析完成，尚未用 Ghidra/IDA 動態確認

---

## 1. 執行環境識別

| 項目 | 值 |
|---|---|
| 格式 | DOS MZ 執行檔 |
| 編譯器 | **Borland C++ (1991 Borland Intl.)** @ `0x048964` |
| 版權 | Copyright 1993, SSI — Strategic Simulations, Inc. |
| 頭部大小 | 21,504 bytes（1,344 paragraphs）|
| 重定位表 | **4,853 個重定位項目**（非常大！說明大量跨段呼叫）|
| 初始 CS:IP | `0000:0000`（MZ stub 立即跳轉）|
| 初始 SS:SP | `4DA2:0080` |

> [!IMPORTANT]
> **4,853 個重定位項目**是非常重要的特徵。這說明 DSUN.EXE 使用了 Borland 的 **overlay 系統**（重疊區段）。這解釋了檔案頭部的 `Runtime overlay error` 錯誤訊息（`0x0056C8`）。Overlay 系統會動態換入/換出程式碼段，這意味著 Ghidra 分析時需要特別處理。

---

## 2. GPL 直譯器識別 — 關鍵發現

### 2a. GPL 函式控制碼（Function Handles）

在 EXE 的 `0x069000–0x06C000` 區域（GPL 程式碼區），找到以下字串：

| 偏移 | 字串 | 意義 |
|---|---|---|
| `0x069990` | `fhGPLI` | **GPL Interpreter** 函式控制碼（第 1 個呼叫點）|
| `0x0699BD` | `fhGPLI` | GPL Interpreter 函式控制碼（第 2 個呼叫點）|
| `0x069BA7` | `fhGPLI` | GPL Interpreter 函式控制碼（第 3 個呼叫點）|
| `0x069BD4` | `fhGPLI` | GPL Interpreter 函式控制碼（第 4 個呼叫點）|
| `0x06A3C8` | `fhGPLX` | **GPL eXecutor/eXit** — 可能是執行完後的返回函式 |
| `0x06A406` | `fhGPLX` | fhGPLX 第 2 個呼叫點 |

> [!NOTE]
> 前綴 `fh` 在 Borland C++ 的 FAR CALL 約定中代表 **far handle**。  
> 字串 `fhGPLI` 是被當成 **GFF 標籤** 使用的 4-字元識別碼。  
> 實際上是 `fhGPLI`（6字元）... 這不是標準 GFF 4字元標籤。  
> **修正**：這些是 `push immediate` 字串，用 `fh` + tag 格式傳入 GFF 查詢函式。

### 2b. GPL 直譯器呼叫序列分析

從 `0x069990` 的 hex dump：

```asm
; 0x069980 — 函式序文 (prologue)
55          PUSH BP
8B EC       MOV BP, SP
83 EC 10    SUB SP, 16        ; 16 bytes 的本地變數
56          PUSH SI
57          PUSH DI

; 0x069990 — 呼叫 GPL 直譯器
66 68 47 50 4C 49    PUSH DWORD 'GPLI'  ; fhGPLI 的 4-char tag
9A AB 05 00 01       CALL FAR 0001:05AB ; FAR CALL 到 GFF 查詢函式
83 C4 0C             ADD SP, 12         ; 清理堆疊 (3 個參數 = 12 bytes)
0B C0                OR AX, AX
74 09                JZ error_branch    ; 如果找不到標籤就跳錯誤
```

> [!IMPORTANT]
> **關鍵發現**：`9A` 是 x86 的 `CALL FAR ptr16:16` 指令。  
> `0001:05AB` 是 GFF 查詢系統的核心函式——它接受一個 4-char tag，  
> 在 GFF 容器中定位對應的資料區塊，並返回指向它的指標。  
> 這個函式就是破解 GFF 格式的入口點。

### 2c. fhGPLX — GPL 執行器

從 `0x06A3B0` 附近：

```asm
; 0x06A3B0 — 函式序文
55          PUSH BP
8B EC       MOV BP, SP
83 EC 0C    SUB SP, 12
83 3E E2 15 01  CMP WORD PTR [15E2h], 1   ; 檢查某個全域旗標
75 03       JNZ continue
E9 1D 02    JMP far_exit

; 0x06A3C0 — 呼叫 GPLX
66 68 47 50 4C 58    PUSH DWORD 'GPLX'  ; fhGPLX tag
9A AB 05 00 01       CALL FAR 0001:05AB  ; 同一個 GFF 查詢函式
```

---

## 3. GFF 查詢函式 — `0001:05AB`（段重定位後的實際位置待定）

這個函式在整個 GPL 區域被反覆呼叫。呼叫約定：

```
參數（32-bit push，用 PUSH DWORD 或兩個 PUSH WORD）：
  - arg1: DWORD ptr (指向緩衝區的 far pointer，接收結果)
  - arg2: WORD (tag 的 high word？或 flags)
  - arg3: DWORD '????'  (4-char GFF tag)
返回值：AX = 0 表示失敗，非 0 = 成功（指標或 handle）
清理：ADD SP, 12（呼叫者清理，cdecl 風格）
```

> [!NOTE]
> 等 Ghidra 確認段表後，`0001:05AB` 的實際文件偏移 =  
> `(段基址 × 16) + 0x05AB + MZ頭大小`。  
> 需要解析重定位表才能正確換算。

---

## 4. 記憶體管理系統 — VMEM

大量 VMEM 錯誤訊息（`0x048C0B` 區段）：

```
VMEM: Invalid initialization    @ 0x048BA1
VMEM: Bad initialization parameters
VMEM: Expanded Memory error     (EMS — LIM 4.0)
VMEM: Extended Memory error     (XMS)
VMEM: XMS Memory error
VMEM: Invalid address argument
VMEM: No more memory available
VMEM: No more STORheaps available
```

**結論**：DSUN.EXE 使用了 SSI 自訂的虛擬記憶體管理器（VMEM），支援：
- 傳統記憶體（Conventional）
- 擴充記憶體（EMS）
- 延伸記憶體（XMS）

這解釋了 GPL 腳本資料如何在 640KB 限制下被管理。

---

## 5. 對話系統 — VCTALK

`VCTALK` @ `0x0491B2`，鄰近的字串：

```
VCTALK   — 對話系統進入點
GET      — 取得物品指令
USE      — 使用物品指令
INFO     — 資訊指令
OPEN     — 開啟指令
USEABLE BY:
NO ONE
HD: %d   — 傷害顯示
LEVEL: %d — 等級顯示
```

**結論**：VCTALK 是遊戲的動詞-名詞式指令解析系統，也是對話觸發的入口。

---

## 6. 壓縮系統線索

```
gpldisk out of memory    @ 0x049D54
Not enough memory in Loadgamefromdisk
Failed Uncompress in Loadgamefromdisk
```

**結論**：
- GPL 腳本從磁碟載入時會做**解壓縮**（`Loadgamefromdisk` 內含 Uncompress 呼叫）
- 壓縮格式未知，但是 Borland C++ 常用 **LZSS 或 RLE**
- `gpldisk` 暗示 GPL 資料被分頁到磁碟，類似虛擬記憶體

---

## 7. GPL 區域熵值分析

| 項目 | 值 |
|---|---|
| 分析範圍 | `0x069000–0x06C000`（12,288 bytes）|
| 唯一位元組數 | 255/256（**幾乎 100% 熵值**）|

> [!WARNING]
> GPL 程式碼區的熵值幾乎 100%，意味著這段是**高度多樣化的機器碼**，不是壓縮資料。  
> 真正的 GPL 腳本資料存在 **GPLDATA.GFF** 和 **RGN*.GFF** 裡，不在 EXE 中。  
> EXE 中的 `fhGPLI` 是執行時動態從 GFF 載入腳本的直譯器框架。

---

## 8. 字型系統

- `FONT` 標籤 @ `0x02A80B`，緊接在 `66 6A 64 66 68` 後面
- `FONT 100` @ `0x04C52F`（`FONT 100` 和 `ICON 100` 相鄰，是 GUI 資源識別碼）
- 格式 `%C%C%C%s`（`0x04C54F`）— `%C` 是 Borland 的 **far char** 格式符

---

## 9. GFF 標籤參照計數

| 標籤 | EXE 中出現次數 | 首次偏移 | 推測用途 |
|---|---|---|---|
| `CHAR` | 20 | `0x048CFA` | 角色資料（最多！）|
| `SAVE` | 16 | `0x04904A` | 存檔 |
| `GPL` | 2 | `0x009D4C` | GPL 腳本 |
| `NAME` | 6 | `0x0497E3` | 名稱資料 |
| `ANIM` | 4 | `0x04A607` | 動畫 |
| `ITEM` | 6 | `0x04A203` | 物品 |
| `FONT` | 2 | `0x02A80B` | 字型 |
| `TEXT` | 1 | `0x067EF7` | 文字 |
| `SPIN` | 1 | `0x08C746` | 法術說明 |
| `LSEQ` | 1 | `0x038AF3` | 音樂序列 |
| `GSEQ` | 1 | `0x038B1F` | 音樂序列 |
| `PSEQ` | 1 | `0x038A83` | 音樂序列 |

---

## 10. 下一步（優先順序）

### P-0（立刻可做，不需 Ghidra）
- [ ] 研究 `GPL ` 標籤在 GFF 容器中的實際二進位格式（用 Python 解析 `GPLDATA.GFF`）
- [ ] 分析 `RGN02.GFF` 裡的 `GPL-*` 條目，比對同一地圖的地圖資料，尋找字串位置

### P-1（需要 Ghidra）
- [ ] 載入 DSUN.EXE，解析 Borland overlay 表
- [ ] 定位 GFF 查詢函式（`CALL FAR 0001:05AB`），交叉參照所有呼叫點
- [ ] 找到 Loadgamefromdisk 函式，識別解壓縮演算法
- [ ] 識別 GPL 直譯器主迴圈（`fhGPLI` 進入後的 dispatch 邏輯）

### P-2（中期）
- [ ] 撰寫 GPL 格式解析器（Python）
- [ ] 提取所有對話字串
- [ ] 建立 GPL opcode 表

---

## 已推翻的假設

_（記錄被資料推翻的初始假設，仿 u5-cht 的紀律）_

| 時間 | 初始假設 | 推翻原因 |
|---|---|---|
| 2026-08-10 | EXE 中可能有 GPL 腳本資料 | GPL 區域高熵 = 純機器碼；腳本在 GFF 檔案中 |
| 2026-08-10 | 字串 `fhGPLI` 是 4-char GFF tag | 實際是 6-char，不符合 GFF tag 規格；是 Borland far handle 標記 |
