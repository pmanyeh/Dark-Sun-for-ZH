# 中文 renderer 動態追蹤階段紀錄

> 日期：2026-08-14  
> 前置文件：`re_11_font100_single_byte_chinese_glyph_proof.md`、`re_12_multiglyph_chinese_phrase_and_resolution_limit.md`、`re_13_font100_16x15_chinese_rendering_proof.md`

## 1. 本階段目標

`re_13` 已證明原版 Dark Sun renderer 可以正常顯示 16×15 中文 glyph；本階段開始處理 256 個單位元組槽位不足的問題，目標是定位：

```text
文字 byte
  → 字碼解析
  → FONT-100 glyph lookup
  → glyph width／advance
  → pixel blit
```

找到上述路徑後，才能設計最小的雙位元組測試：讓兩個輸入 bytes 只取出一個中文字 glyph，並正確更新游標與換行寬度。

## 2. 已確認的中文顯示能力

今天開始 renderer 追蹤前，已完成下列實機驗證：

1. `FONT-100` 全域高度由 9 改為 15 後，遊戲可以正常載入。
2. 六個暫用 ASCII glyph 槽可替換成 16×15 中文字形。
3. 測試句 `中文顯示成功` 六字均可在遊戲對話框完整顯示。
4. 中文 glyph 的 advance 可設為 16，沒有被原英文 7-pixel 寬度限制裁切。
5. 原英文 glyph 補高到 15 rows 後仍能與中文共存。

因此下一個問題已不是「原 renderer 能否畫中文」，而是「如何突破 256 glyph slots，並讓兩個 bytes 被當成一個 glyph」。

## 3. 原生 DOSBox-X AI bridge 已可用

本機 `D:\git\DOSBox-X-AI` 有一份具備原生 TCP debugger bridge 的 DOSBox-X：

```text
D:\git\DOSBox-X-AI\dosbox-src\bin\x64\Release\dosbox-x.exe
TCP: 127.0.0.1:9876
Python client: D:\git\DOSBox-X-AI\ai\dosbox_client.py
```

已實際驗證可使用：

- 暫停／繼續 guest CPU；
- 取得真實 CPU registers 與 segments；
- 讀取指定 selector 的記憶體；
- 反組譯目前或指定位置的程式碼；
- 設定、列出及刪除實體程式碼 breakpoint；
- step into／step over。

GUI debugger 的鍵盤輸入容易受到 Windows 焦點或文字選取模式影響。本次後半已改成完全透過 TCP bridge 設定程式碼 breakpoint，並以 `list_breakpoints()` 與 `get_debug_status()` 回讀驗證。後續應優先沿用此方式，不再依賴 GUI 命令輸入。

## 4. 記憶體掃描結果

### 4.1 `FONT-100` 未以原始 chunk 形式常駐

在對話畫面出現後暫停遊戲，掃描目前可見的程式、資料與堆疊 selectors，沒有找到：

- 修改後 `FONT-100` 的完整標頭；
- 六個 16×15 中文 glyph 的原始 pixel records；
- `CJK PHRASE TEST`／`@#$[]*` 等測試字串。

這表示至少有下列一種情況成立：

- `FONT-100` 載入後被拆成另一種 runtime 結構；
- glyph 資料位於目前尚未列出的 protected-mode selector；
- 資料位於 EMS／動態映射頁，只在使用期間短暫可見；
- 對話文字在顯示前又經過 token／中介結構處理。

不能再假設可由 `0000:0000` 掃描整個 1 MB 實體記憶體：遊戲正在 protected mode，selector 解析並非簡單的 `segment << 4`。

### 4.2 EMS 線索

Debugger 輸出確認：

```text
EMS page frame at 0xE000-0xEFFF
```

這與「字型或資源只在需要時映射」的可能性相符，但目前尚未直接證明 `FONT-100` 位於 EMS。此項仍是待驗證假設，不可寫成結論。

## 5. 已定位但排除的圖形呼叫鏈

### 5.1 可重現的常駐 blit 入口

改用 TCP bridge 設定原生程式碼 breakpoint：

```text
11A4:69C4
```

Breakpoint 清單與 CPU 狀態均確認命中：

```text
11A4:69C4  mov dl,[si]
```

其所在函式入口為：

```text
11A4:672A
```

函式會：

1. 從參數取得來源 image／RLE stream；
2. 解碼 run-length 資料；
3. 建立 4-plane strip；
4. 透過 VGA sequencer port `03C4/03C5` 選擇 plane；
5. 將結果寫入 `A000` 顯示記憶體。

### 5.2 回溯出的呼叫鏈

在 `11A4:685B` 的 `RETF` 後 step into，取得直接呼叫者：

```text
222E:31C2  call 11A4:672A
222E:31C7  add  sp,000E
```

再於 `222E:31D4` 的 `RETF` 後 step into，取得上一層：

```text
5C8E:0A42  call 222E:3180
5C8E:0A47  add  sp,000E
```

因此目前可重現的鏈為：

```text
5C8E:0A42
  → 222E:3180
    → 11A4:672A
      → VGA planar output
```

### 5.3 排除結論

這條鏈屬於通用 image／animation update 與 RLE/VGA blit，不是已證實的 `FONT-100` glyph lookup。它可以作為畫面輸出的底層參考，但不應再從任意 VGA 像素沿此鏈追查中文 renderer，否則容易反覆命中背景、面板或動畫。

## 6. 本次除錯方法上的修正

曾嘗試透過 GUI debugger 輸入 `BPM`。因輸入焦點被移動，加上 debugger 視窗進入文字選取狀態，部分命令實際未進入命令列。後續已用下列程序消除不確定性：

1. 由 TCP bridge 呼叫 `pause_execution()`；
2. 使用 `set_breakpoint("selector:offset")` 設程式碼斷點；
3. 立即以 `list_breakpoints()` 確認地址與 enabled 狀態；
4. `continue_execution()` 後等待命中；
5. 以 `get_debug_status()` 確認 `stopped=true` 與實際 `CS:EIP`；
6. 完成後刪除斷點並再次確認 breakpoint list 為空。

這套程序已成功重現 `11A4:69C4`、`11A4:685B` 與 `222E:31D4`，後續應作為標準動態追蹤流程。

## 7. 明日續作方向

下一輪不再從任意 VGA pixel 往上追，而直接鎖定「文字資料消費端」。建議順序：

1. 建立只包含獨特短字串與單一替換 glyph 的最小對話測試，減少背景與動畫噪音。
2. 在 GPL 解壓縮／句子組合完成處取得實際文字 buffer 的 selector:offset。
3. 對文字 buffer 使用 debugger 的 memory watchpoint；若 TCP bridge 仍未公開 memory breakpoint，應優先為 bridge增加受限的 memory-watchpoint API，避免 GUI 焦點問題。
4. 在文字 byte 被讀取時記錄 `CS:EIP`，辨認逐 byte 迴圈、控制碼分支與字串終止條件。
5. 從該迴圈追到 glyph index／offset table lookup，確認 width 與 line-wrap 是否在同一條路徑。
6. 先做固定映射實驗，例如一組測試 lead/trail bytes → 現有「中」glyph。
7. 驗證兩 bytes 只消耗一個 glyph、advance 16、下一字不錯位且換行正確。

## 8. 階段狀態

```text
[完成] 英文文本抽取、修改、重封裝、導入與實機驗證
[完成] 單一 8×9 中文 glyph 顯示
[完成] 六字單位元組暫用槽顯示
[完成] 16×15「中文顯示成功」實機驗證
[完成] 原生 TCP debugger bridge 連線與程式碼 breakpoint 流程
[完成] 排除通用 RLE／VGA blit 呼叫鏈
[待辦] 定位解壓縮後文字 buffer
[待辦] 定位逐 byte 文字消費迴圈
[待辦] 定位 FONT-100 glyph lookup／width／wrap
[待辦] 固定雙位元組 → 單一 glyph 最小實驗
```

