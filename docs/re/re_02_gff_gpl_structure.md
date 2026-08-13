# docs/re/02-gff-format-and-gpl-structure.md
# GFF 格式完整解析 + GPL 腳本結構

> **輸入**：`GPLDATA.GFF`（1,383,098 bytes）、`RGN02.GFF`（122,820 bytes）  
> **工具**：Python 靜態解析  
> **日期**：2026-08-10  
> **狀態**：GFF 容器格式已確認；GPL 腳本內容加密待破解

---

## 1. GFF 容器格式（已確認）

### 1a. 檔案頭部（Header — 28 bytes）

```
Offset  Size  值（GPLDATA.GFF）   說明
──────  ────  ─────────────────   ────────────────────────
0x00    4     47 46 46 49          Magic: "GFFI"
0x04    4     00 00 03 00          版本 = 3 (little-endian word: 0x0003)
0x08    4     1C 00 00 00          Entry table offset = 0x1C = 28（緊接頭部）
0x0C    4     BE 09 15 00          資料區大小 = 0x1509BE = 1,378,750 bytes
0x10    4     F4 02 00 00          Entry 數量 = 0x2F4 = 756
0x14    8     (reserved/padding)
```

**兩個 GFF 檔案都確認相同格式，僅數值不同：**
| 檔案 | 大小 | Entry 數 | 資料大小 |
|---|---|---|---|
| GPLDATA.GFF | 1,383,098 | 756 | 1,378,750 |
| RGN02.GFF | 122,820 | 120 | 122,700 |

### 1b. Entry Table 結構（位於 offset 0x1C 開始）

**尚未直接解出 entry table 格式**——偏移 0x1C 的資料看起來是壓縮/二進位，不是整齊的目錄表。這表示：
- GFF 的 entry table 可能本身也被壓縮
- 或者真正的目錄在檔案末尾（常見於 PKG/archive 格式）
- 或者偏移 0x1C 的含義與假設不同

> [!WARNING]
> **修正假設**：0x08 處的 0x1C 可能是「**第一個資料區塊的偏移**」，  
> 而不是「entry table 的偏移」。Entry table 可能位於 `0x0C` 所指向的  
> 資料末端（0x1509BE 之後），類似 ZIP 格式的「中央目錄在尾端」。

### 1c. 真正的目錄結構 — 倒推法發現

GPL tag 在 GPLDATA.GFF 位於 `0x150C94`（距離檔案末端 32KB），  
這個區域的結構非常清晰：

```
Offset    Hex                                    說明
────────  ─────────────────────────────────────  ─────────────────
150C84    26 00 00 00                             前一個 entry? = 0x26
150C88    08 00 00 00                             count? = 8
150C8C    63 00 00 00                             = 99
150C90    01 00 00 00                             = 1
────────  ─────────────────────────────────────  ─────────────────
150C94    47 50 4C 20                             TAG = "GPL " ← GPL 區塊頭
150C98    D9 00 00 80                             0x800000D9 (high bit set = compressed?)
150C9C    D9 00 00 00                             count = 0xD9 = 217 (腳本數量)
150CA0    08 00 00 00                             sub-entry 大小 = 8? 或 stride
150CA4    01 00 00 00
150CA8    01 00 00 00
150CAC    D9 00 00 00                             再次確認 217
150CB0    00 00 00 00                             padding
────────  ─────────────────────────────────────  ─────────────────
150CB4    (GPL entry table starts here)
```

---

## 2. GPL 腳本條目表格（已解析！）

從 `0x150CB4` 開始，每個條目 = **12 bytes**：

```
struct GplEntry {
    uint32_t id;     // 腳本 ID（16進位，如 0x1012, 0x106A...）
    uint32_t offset; // 腳本資料在 GFF 檔案中的偏移
    uint32_t size;   // 腳本資料大小（bytes）
}
```

**已解析的前 30 個 GPL 條目（GPLDATA.GFF）：**

| Index | Script ID | File Offset | Size | 備註 |
|---|---|---|---|---|
| 0 | `0x00000000` | `0x0011E828` | 608 | 主腳本？ |
| 1 | `0x00001012` | `0x0011EA88` | 598 | |
| 2 | `0x00001068` | `0x0011ECDE` | 547 | 含 `ZYZYZY` |
| 3 | `0x00001069` | `0x0011EF01` | 641 | |
| 4 | `0x0000106A` | `0x0011F182` | 327 | |
| 5~11 | `0x106B`~`0x1071` | ... | 300~400 | |
| 20 | `0x000010D4` | `0x0012074A` | 353 | 含 `nkjj\|klmi` |
| 21 | `0x000010D5` | `0x001208AB` | 354 | 含 `hhlkmo` |

**總計：217 個 GPL 腳本**（這些是主要的對話/劇情腳本！）

---

## 3. GPL 腳本資料加密分析（最關鍵）

### 3a. 觀察到的模式

在 GPL 腳本資料（如 entry 2, offset `0x0011ECDE`）中，可見：
```
ZYZYZYZYZYSS...
```

在 entry 20~29 中可見：
```
nkjj | klmi | mhkjhihihhffhgjj
hhlkmo
jkjjlljkjkjk
WUVVWU | SVUUVWV
VTTUWWXX | TTUUWX
```

### 3b. 加密類型判斷

這些字元特徵強烈暗示：

**假設 A：XOR 加密（最可能）**

字母 `WUVVWU`, `ZYZYZY` 的 ASCII 值：
- `Z` = 0x5A, `Y` = 0x59 → 差值 1，交替出現
- `W` = 0x57, `U` = 0x55, `V` = 0x56 → 連續範圍的值

若原文是空位元組 `0x00` 或低值 ASCII，XOR 後在 0x50~0x5F 範圍 → key ≈ 0x56 附近？

**假設 B：查表替換（Caesar-like）**

將這些值偏移固定量：
- `Z`(0x5A) - 0x20 = 0x3A (`:`)
- `Y`(0x59) - 0x20 = 0x39 (`9`)
- `n`(0x6E) - 0x20 = 0x4E (`N`)
- `k`(0x6B) - 0x20 = 0x4B (`K`)

若偏移 0x20：`nkjj` → `NKJ J`（可能是英文！）

**假設 C：LZSS/LZW 壓縮後再加密**

EXE 中的 `Failed Uncompress in Loadgamefromdisk` 明確說明有解壓縮步驟。  
可能是：壓縮 → 加密，或 加密 → 壓縮。

> [!IMPORTANT]
> **驗證優先順序**：  
> 1. 先試 **偏移 -0x20**（`nkjj` → `NKJJ`？）  
> 2. 再試 **XOR 0x7E**（常見的簡單混淆）  
> 3. 再試 **XOR 0x56**  
> 4. 最後才考慮 LZSS 壓縮

---

## 4. 第二個 GPL 區塊（不同格式）

在 `0x151084` 的第二個 GPL tag 有不同結構：

```
field+4 = 0x000000D9 = 217 (同樣的腳本數量，但沒有高位旗標 0x80)
field+C = 0x0000001C = 28  (條目表偏移從此開始)
```

條目格式也是 12 bytes（id + offset + size），但偏移指向的資料**完全不同**：
- Entry 0: id=`0x2640`, off=`0x00000003`, sz=`0x3AED` → 指向 GFF 頭部附近！

這可能是第二個 GPL 區塊是**索引/目錄**，指向壓縮後的完整腳本資料。

---

## 5. 執行計畫：破解 GPL 加密

### 立即可做（不需 Ghidra）

```python
# 試驗各種簡單變換
for xor_key in [0x00, 0x20, 0x40, 0x56, 0x7E, 0xFF]:
    decrypted = bytes(b ^ xor_key for b in gpl_data[:64])
    print(f"XOR {xor_key:02X}: {decrypted}")
    
# 試減法偏移
for offset in range(-0x40, 0x40):
    shifted = bytes((b - offset) & 0xFF for b in gpl_data[:64])
    # 計算可讀字元比例
    readable = sum(1 for b in shifted if 0x20 <= b < 0x7F)
    if readable > 30:  # 超過 30 個可讀字元很可疑
        print(f"Offset {offset:+03d}: {shifted} (readable={readable})")
```

### 需要 Ghidra 確認

- 找到 `Loadgamefromdisk` 函式的反組譯
- 識別解壓縮/解密的實際演算法
- 取得 XOR key 或壓縮參數

---

## 6. 下一步

| 優先 | 工作 | 預計難度 |
|---|---|---|
| 🔴 P0 | 對 GPL 資料試驗 XOR/偏移解密 | 低（1 小時）|
| 🔴 P0 | 用 Ghidra 找 Loadgamefromdisk 函式 | 中（1 天）|
| 🟡 P1 | 完整解析 GFF entry table 格式 | 中（半天）|
| 🟡 P1 | 解包所有 217 個 GPL 腳本 | 低（有工具後自動化）|
| 🟢 P2 | 建立 GPL opcode 表 | 高（可能數週）|

---

## 7. 已推翻的假設

| 假設 | 推翻原因 |
|---|---|
| GPL 腳本在 EXE 中 | GPL 程式碼區是純機器碼；腳本在 GFF 檔案 |
| GFF 頭部 0x08 = entry table offset | 0x1C 偏移的資料不是整齊的目錄 |
| GPL 資料完全無法讀取 | 發現部分 ASCII 字元（`nkjj` 等），可能只是簡單加密 |
| 第二個 GPL 是副本 | 兩個 GPL 區塊結構不同，可能是壓縮資料+索引的配對 |
