# CJB1 按字 direct-read 跨 bank 實機證明

> **2026-08-15 後續修正：**本頁保留早期 15-row prototype 的實驗紀錄。法術說明 UI
> 後來證明 `36AA:5534` 以後會被動態資料覆寫，因此目前可玩版不再使用
> `36AA:545A..5557` 與常駐 handle；v5 改用精確的 218 bytes
> `36AA:545A..5533`，每個 glyph 都執行 open/read/close。最新執行期證明見
> `re_35_relocation_safe_ebox_base94_wrap_and_spell_runtime_proof.md`。

> 日期：2026-08-14  
> 前置文件：`re_28_scratch_cache_exe_install_and_load_smoke_test.md`

## 1. 結論

正式 CJB1 bank 已不需載入 conventional-memory block。新版 resident cache 保持一個
DOS file handle，依 CJK ID 直接 seek/read directory entry，再把 242-byte glyph
record 讀入 FONT scratch。ID 255 與 256 已動態通過 bank 0→1 邊界：

```text
ID 255 -> C0.BIN directory[255] -> record 0xF51E -> FONT scratch
ID 256 -> C1.BIN directory[0]   -> record 0x0410 -> FONT scratch
```

兩筆 scratch 均與正式 bank record 逐 byte相同，且彼此不同。

## 2. 實機推翻的兩個假設

1. `0x9718` 在磁碟 EXE 是 zero run，但遊戲啟動後會被 overlay/runtime workspace
   覆寫，不能作 resident code cave。
2. 即使只配置一個 62,992-byte bank，DOS `int 21h/AH=48h` 仍回傳 error 8，表示
   conventional memory 不足。

最終 code 改放先前多輪證明穩定的 resident 區：

```text
wrappers/state/tables  0x53A6..0x5419
resolver               0x5420..0x5459
direct-read cache      0x545A..0x5557
```

啟動後已對 state、filename table、resolver 與 cache code 全部逐 byte 比對成功。

## 3. Direct-read 流程

每個 CJK glyph 執行：

1. high byte 決定 `C0.BIN`～`C3.BIN`；跨 bank 時關閉舊 handle、開啟新檔。
2. seek 到 `16 + local_index * 4`。
3. 讀取 `<u16 index, u16 record_offset>` 到 4-byte resident buffer並驗證 index。
4. seek 到 record offset。
5. 將 242 bytes 直接讀到 runtime FONT payload `+0x3640`。
6. 將 legacy marker `0x7F` offset 設為 `0x3640`，回到既有 width/render path。

任何 DOS call、短讀或 index mismatch 都回傳單一 `?` replacement。

## 4. ID 255 動態證據

```text
resolver AX              0x00FF
current bank             0
file handle              0x000A
directory bytes          FF 00 1E F5
record offset            0xF51E
read result AX           0x00F2 (242)
scratch SHA-256          8b709090adbebe28d08eca777d1ac0b61de5ea26fdb4f303f1fa938198f57c1e
C0.BIN record SHA-256    8b709090adbebe28d08eca777d1ac0b61de5ea26fdb4f303f1fa938198f57c1e
```

## 5. ID 256 動態證據

```text
resolver AX              0x0100
current bank             1
directory bytes          00 00 10 04
record offset            0x0410
read result AX           0x00F2 (242)
scratch SHA-256          1b81b6e1d0c1dc955f9cc8c43414f3035633c545b02657ee7251ee19d73abfbc
C1.BIN record SHA-256    1b81b6e1d0c1dc955f9cc8c43414f3035633c545b02657ee7251ee19d73abfbc
```

marker entry 在兩筆均為 `0x3640`。第二筆 scratch 與第一筆不同，排除 cache 未更新。

## 6. 畫面確認

所有 debugger breakpoints 移除並恢復執行後，畫面顯示 mapping ID 255／256：

```text
ID 255  U+5F92  徒
ID 256  U+5F97  得
```

後方 `SCRATCH BANK 0-1 TEST...`、下一行原有英文、換行與 MORE 均正常，證明
width/layout 與 glyph pass 都能使用 direct-read scratch cache。

使用者第一眼將「徒」辨認成「甲」，顯示暫用 Noto Sans TC 縮圖的細部辨識度不足；
debugger 的 ID、directory offset、record SHA-256 均確認載入的是 ID 255 record，因此
這是暫用字源的品質問題，不是 mapping、bank selection 或 cache 錯字。後續應接入
使用者合法自備的倚天 `STDFONT.15`／`SPCFONT.15` 原生點陣；不應把微調 Noto 當成
最終字形方案。
