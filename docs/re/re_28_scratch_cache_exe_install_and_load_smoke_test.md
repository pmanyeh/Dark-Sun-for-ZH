# Scratch-cache EXE 安裝與載入 smoke test

> 日期：2026-08-14  
> 前置文件：`re_27_resident_scratch_cache_loader_prototype.md`  
> 狀態：早期 code-cave / allocation 方案已否決；由 re_29 取代

## 1. 結論

Scratch-cache 原型已從獨立 assembly 推進為可安裝的 DSUN.EXE patch，並完成獨立遊戲
副本封裝與 DOSBox-X guest-memory image smoke test。此結果不等於已確認進入遊戲畫面。

```text
algorithmic resolver  58 bytes at 0x5420
resident cache        372 bytes at 0x9718
patched DSUN SHA-256  0e032b2b9162e11a742312a0208f4e5c858a56f1fca775aab12916f39b40c4eb
```

`tools/patch_dsun_scratch_cache.py` 對每個既有 instruction 與 zero cave 先作 expected-byte
比對，任何版本差異都會拒絕寫入。resolver 的 near call 經反組譯確認為：

```text
36CF:544C  call 36CF:9718
```

## 2. 單一 active bank（已否決）

resident routine 已由「一次載入四 bank」改成最多只保留一個 active bank：

1. ID high byte 等於 current bank 時直接使用。
2. 跨 bank 時以 `int 21h/AH=49h` 釋放舊 segment。
3. 依 bank size 用 `48h` 配置 1,739～3,937 paragraphs。
4. 開啟對應 `CJK0.BIN`～`CJK3.BIN` 並完整讀入。
5. 任一步失敗都回傳單一 `?`，不進入 glyph copy。

這把 conventional-memory 常駐需求由約 216 KiB 降至最多 62,992 bytes，但實機
`int 21h/AH=48h` 仍回傳 error 8，因此容量仍不可接受。

另外，原選的 `0x9718` zero run 會在遊戲啟動後被 runtime workspace 覆寫；磁碟上
為零不代表 resident-safe。這兩項均由 re_29 的互動追蹤修正。

## 3. 完整 probe package

已在 `scratch_test/cjk_scratch_runtime` 建立不覆蓋舊測試的獨立安裝，包含：

- patched `DSUN.EXE`；
- `CJK0.BIN`～`CJK3.BIN`；
- appended 242-byte scratch record 的 FONT-100；
- 使用 `^#d`／`^#e`（ID 255／256）的 GPL-2。

FONT-100 與 GPL-2 重封裝進 GFF 後再抽取，SHA-256 均與輸入完全一致。

## 4. DOSBox-X 動態載入證據

修正含空白 conf 路徑的啟動 quoting 後，TCP bridge 在 conventional memory 找到
resident routine signature：

```text
physical hit       0x40408
cache offset       0x09718
derived code base  0x36CF0
runtime CS         36CF
```

因此 patched executable 的 image 曾載入 guest memory，且 resident code 位址與
near-call 計算一致。`36CF:544C` breakpoint 可正常建立。但當時 CPU 位於 BIOS
keyboard idle；signature 也可能是已結束程式留下的 conventional-memory remnants，
所以不能據此宣稱遊戲已成功啟動。

## 5. 尚未完成的動態證明

在沒有 synthetic keyboard/mouse API 的 TCP bridge 下，十秒自動執行停在 BIOS
keyboard idle，且當時以 hidden window 啟動，無法判定它是在遊戲等待輸入、批次檔
等待，或已返回 DOS。故本輪只保留 image-load 證據；尚未證明遊戲啟動，也不能由
breakpoint 未命中推論 cache 成敗。

下一個 checkpoint 是在可互動 DOSBox 視窗中進入開場對話，依序記錄：

1. `36CF:544C` 的 AX = `00FF`、`0100`；
2. current bank 從 0 切到 1，且 segment 被替換；
3. FONT scratch 242 bytes 分別等於正式 ID 255、256 records；
4. `36CF:06FE` width 為 16；
5. 畫面、MORE 與回頁重畫均正常。
