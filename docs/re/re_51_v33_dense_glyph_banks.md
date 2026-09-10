# v33 固定槽位 dense glyph banks

> 日期：2026-08-17  
> 狀態：已建置並啟動，等待實機確認

## 根因

v31 已撤回 `%Fs` 實驗修補，因此 `STR`、`DEX` 等英數恢復；但對話與法術說明
仍有大量 `?`。缺字分布顯示問題集中在：

- bank 1 的 index 226 之後；
- bank 2 的 index 27 之後。

v18 bank builder 只輸出 `active` mapping entries，恰好略過 bank 1/index 226 與
bank 2/index 27 兩個歷史槽位，使這兩個 bank 各只有 255 筆記錄。runtime loader
並不查 sparse directory，而是依固定 record 大小直接 seek；缺一筆後，後面所有
index 都讀到錯誤記錄，因而顯示 `?`。

## 修正

`cjk_localization_pipeline.py build-banks` 現會輸出 mapping 中的全部歷史 ID，包含
inactive entries；`verify-banks` 同樣驗證全部 ID，而非只驗證 active entries。
新封包：

```text
scratch_test/formal_cjk_fusion_10x10_v19_dense
scratch_test/cjk_display_staging_v33_dense_banks
```

槽位數：

```text
bank 0: 256
bank 1: 256
bank 2: 256
bank 3: 256
bank 4: 256
bank 5:  34
total mapping IDs verified: 1314
```

v33 保留累積 GPL2～6、GPLI-1、NAME-1 中文，停用已否決的物件 `%Fs` 實驗，並已
複製 v31 的 `DARKRUN.GFF`（SHA-256 比對一致）。44 項 Python 測試通過。

物件右鍵資訊卡亂碼仍是獨立且尚未解決的問題。
