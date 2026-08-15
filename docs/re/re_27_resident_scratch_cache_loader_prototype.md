# Resident scratch-cache loader 原型

> 日期：2026-08-14  
> 前置文件：`re_26_cjb1_loader_contract_and_full_bank_verification.md`  
> 狀態：本版整-bank allocation 已由 re_29 實機否決；改採按字 direct-read

## 1. 本輪成果

本文件記錄最初的整-bank resident 構想。後續實機在 DOS `AH=48h` 得到 error 8
（conventional memory 不足），因此現行 `tools/cjk_scratch_cache.asm` 已改為按字
direct-read；最終動態證據見 re_29。

已建立 `tools/cjk_scratch_cache.asm` 的 16-bit resident routine，以及
`tools/build_cjk_scratch_probe.py` 的資產 staging 工具。原型採以下資料流：

```text
base-94 resolver -> u16 CJK ID
  -> （原構想）第一次使用時以 DOS int 21h 載入 CJK0.BIN..CJK3.BIN
  -> high byte 選 far bank segment
  -> low byte 選 CJB1 directory entry
  -> far rep movsb 複製 242-byte record
  -> FONT-100 + 0x3640 scratch record
  -> legacy marker 0x7F renderer
```

此構想避開單一 FONT segment 的 64 KiB 限制，但 conventional-memory 預算不足，
不可作為正式方案。

## 2. DOS 記憶體配置

四個正式 bank 的配置大小為：

| Bank | Bytes | Paragraphs |
|---:|---:|---:|
| 0 | 62,992 | 3,937 |
| 1 | 62,992 | 3,937 |
| 2 | 62,992 | 3,937 |
| 3 | 27,814 | 1,739 |

resident routine 以 `int 21h/AH=48h` 配置，各 bank 以 `3Dh` 開啟、`3Fh` 一次讀入、
`3Eh` 關閉。segment pointers 存在 CS resident table，因此切換 FONT payload DS/ES
時不依賴遊戲 data segment。

## 3. Scratch slot

staging 工具要求輸入 FONT payload 恰為 `0x3640` bytes，再附加一筆 242-byte record。
初始內容使用正式 ID 255；ID 256 來自另一個 bank 且 record bytes 不同，可在下一輪
動態測試中證明跨 bank refill，而非重畫舊 cache。

```text
scratch offset  0x3640
record size     242
marker entry    legacy 0x7F / payload +0x0206
```

## 4. 靜態建置證據

GNU assembler `.code16` 已成功組譯 resident routine，並以 i8086 disassembly 核對
segment override、DOS calls、directory lookup、`rep movsb` 與 marker write：

```text
binary bytes  310
SHA-256       59706d1e28353e03956f60437932dffc0e1839e1bd6cfff5cbbc6c301f1de55e
```

staging 結果為四個 `CJK?.BIN` 與 `FONT-100.scratch.bin`。自動測試增至十項；新增
測試確認全部 881 records 都恰為 242 bytes，且 ID 255／256 的 record 不相同。

## 5. 尚未完成的部分

本文件只記錄靜態原型，不把它寫成 runtime proof。下一輪仍須：

1. 把 routine 安裝到已確認的 EXE zero cave，並讓 algorithmic resolver 保留暫存器後呼叫它。
2. 重封裝 scratch FONT，將四個 8.3 bank files 放入遊戲目錄。
3. 建立只含 ID 255／256 的 GPL 測試句。
4. 在 bank segment table、scratch `+0x3640` 與 glyph width read 設動態斷點。
5. 驗證首次 lazy load、跨 bank refill、width/draw passes 與 MORE 回頁。
