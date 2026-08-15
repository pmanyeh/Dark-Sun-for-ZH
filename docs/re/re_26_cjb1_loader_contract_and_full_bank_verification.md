# CJB1 loader contract 與完整字庫驗證

> 日期：2026-08-14  
> 前置文件：`re_25_utf8_catalog_transport_compiler.md`

## 1. 結論

正式 881 字、四個獨立 `CJB1` banks 已由與未來 runtime loader 相同的 lookup contract
逐筆解析通過。新增命令：

```powershell
python tools/cjk_localization_pipeline.py verify-banks `
  --package scratch_test\formal_cjk_pipeline\cjk-bank-set.json
```

本次重新建置與驗證結果：

```text
verified_banks=4
verified_glyphs=881
max_record_bytes=242
```

四個 bank 的 bytes 與 SHA-256 和 re_22 記錄完全相同，證明 pipeline 修改沒有改變
任何正式字形資料。

## 2. Loader contract

`read_bank()` 現嚴格驗證：

1. `CJB1` magic、version 與 expected bank ID。
2. directory 位於 payload 範圍內。
3. 每個 local index 小於 256 且不重複。
4. 每個 u16 record offset 位於 directory 之後。
5. `u16 width + width * height` 必須精確結束於下一筆 record 或檔尾；不容許截斷、
   重疊或未描述的間隙。

`glyph_record_for_id()` 固定使用：

```text
bank  = cjk_id // 256
index = cjk_id % 256
```

並在 bank 或 index 缺失時立即失敗。這就是下一版 16-bit far-bank／scratch-cache
resolver 必須實作的資料選取語意。

## 3. 可重複建置 fingerprint

第一次驗證正確偵測到 bank-set 的舊 `mapping_sha256` 已因 transport 狀態註記更新而
失效，但 CJK ID 與 glyph identity 並未變更。為避免 metadata 造成假性 rebuild，
bank package 現另存 canonical `mapping_fingerprint`，只涵蓋：

- mapping format/version 與 bank capacity；
- 每筆 ID、Unicode character、bank、index、active。

描述文字與 occurrence count 不影響 fingerprint；任何會改變字庫選取的欄位仍會使
驗證失敗。整檔 `mapping_sha256` 繼續保留作 provenance。

## 4. 自動測試

測試現為九項，全部通過。新增測試涵蓋 CJB1 build/read round trip、跨 bank 的
ID 256 lookup、缺字、截斷 record，以及 fingerprint 的 metadata/identity 邊界。

## 5. 下一步

資料端現在已有明確且完整驗證的 loader contract。下一步把 `glyph_record_for_id()`
的語意移植到 16-bit patch：載入目前 bank 的 far pointer，依 local index 找到最多
242-byte record，複製到 FONT segment 內固定 scratch record，再讓既有 marker
trampoline 繪製。第一個實機 checkpoint 應跨 bank 0/1 顯示 ID 255 與 256，並在
width pass、glyph pass、MORE 回頁都驗證 cache refill。
