# docs/re/03-gpl-bytecode-and-text-findings.md
# GPL Bytecode 結構分析與文字壓縮特徵報告

> **對象**：`GPLDATA.GFF` 內 217 個 GPL 區塊、`RESOURCE.GFF`、`RGN*.GFF`  
> **工具**：`decrypt_gpl.py` / `inspect_gpl.py` / `scan_dialogue.py`  
> **日期**：2026-08-10  
> **結論**：GPL 區塊為 Bytecode 邏輯腳本；對話文字已被自訂壓縮或編碼

---

## 1. GPL 區塊結構驗證

透過實測 217 個 GPL 區塊，確認了 GPL 區塊的二進位標頭格式：

```
Offset  Size  類型         說明
──────  ────  ───────────  ──────────────────────────────────────────
0x00    4     uint32_le    Block Length Header (區塊精確長度)
0x04    2     uint16_le    Sub-Header 常數（通常為 0x0001）
0x06    2     uint16_le    Opcode Count / Header Flag（如 0x000A / 0x000F）
0x08    ...   Bytecode     GPL 程序指令集、變數與路徑資料
```

所有 217 個區塊的首 4 bytes 均精確等於該區塊的大小（例如 Block 0 的首 4 bytes 即為 `608`），證實 **區塊並未整體進行二進位容器層層加密**。

---

## 2. GPL Bytecode 內容特徵分析

在個別 GPL 區塊內部，觀察到高度結構化的位元組模式：

1. **路徑與走位向量代碼 (Movement/Path Vectors)**：
   * 在 Block 20 (`0x10D4`)、Block 21 (`0x10D5`) 等區塊中，出現大量的 `nkjj`, `klmi`, `mhkjhihihhffhgj>`, `hhlkmo` 等 ASCII 字元串。
   * 這些字元集中在 `f` ~ `o` 的範圍內，代表 RPG 地圖中 NPC 的相對走位、方向向量與動作鏈（類似 VIM 方向控制）。
2. **對話樹分支與狀態矩陣 (State/Choice Matrices)**：
   * 出現如 `ZYZYZYZYZYSS`、`adca` 等重複模式，為對話選擇項目的 State Transition Table。

---

## 3. 對話文本壓縮特徵與瓶頸確認

透過全域掃描 `RESOURCE.GFF` 與 `RGN*.GFF`，**確定遊戲中沒有任何明文 English 劇情對話**。

這說明：
* **劇情對話並非獨立文字檔**，而是被打包/編碼在 `.GPL` 二進位腳本中。
* **對話文字採用了自訂的壓縮或字元編碼**（例如 5-bit packed ASCII、Huffman Tree 或自訂表格）。
* 單純的 XOR / 簡單位移（Caesar cipher）無法解出自然英文，證實文字經過了結構化編碼。

---

## 4. 下一步策略建議

有了這些實體證據後，解決 GPL 文字解密的雙軌計畫如下：

```
【軌道一：Ghidra 靜態逆向（最根本）】
用 Ghidra 載入 DSUN.EXE
 └─► 追蹤 0x069990 的 fhGPLI (GPL Interpreter)
      └─► 找到字串/文字讀取指令 (String Decompressor / Char Lookup)
           └─► 複製解密邏輯，寫出 Python GPL 對話提取器

【軌道二：明文/選單雙軌並行（快速建立中文化成果）】
先翻譯已確認明文的 NAME (物品) 與 SPIN (法術說明)
 └─► 寫出 GFF 重新封包工具
      └─► 注入改過的英文/中文字體，先完成物品與法術的中文化補丁
```
