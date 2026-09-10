# GPL-6 巴爾卡札場景翻譯批次（2026-08-17）

## 1. 本輪範圍

依使用者最新指示，暫緩 DOSBox-X-AI 自動操作與物品 renderer 追蹤，先恢復翻譯工作。
本輪選擇情節完整、規模適中的 `GPL-6`（巴爾卡札／達戈拉爾場景）：

- `GPL-6` 共有 53 個唯一翻譯單元；
- 原有 3 個已翻譯名稱：達格、哈爾頓、加恩；
- 本輪完成其餘 50 個單元，全部標為 `translated_unreviewed`；
- 新增／統一巴爾卡札、達戈拉爾、無名者、哈蒙德、瑪格拉、巴布魔、弗洛魔、
  恐懼之花等譯名。

翻譯已同步到：

```text
localization/catalog/dialogue_units.csv
localization/catalog/dialogue_units.json
localization/catalog/localization_manifest.csv
localization/catalog/localization_manifest.json
localization/proper_noun_glossary.json
```

## 2. 現有匯入器限制

53 個單元依來源可分為：

- 49 個 `inline/compressed`；
- 4 個 `text:gstring` 名稱（達格、哈爾頓、加恩、哈蒙德）。

4 個名稱仍需未完成的 TEXT 字串表匯入器。

49 個 inline 單元中，有 11 個選項共用兩個 GPL menu 指令位置：

```text
GPL-6@0x0260：9 個選項
GPL-6@0x0842：2 個選項
```

現有 `compile_gpl_dialogue_patch.py` 會正確拒絕「多個編輯指向同一指令位置」，因此本輪沒有
繞過檢查；11 條翻譯保留在 catalog，待多選項匯入器支援後再加入遊戲。

## 3. 安全 GPL 編譯結果

其餘 38 個唯一單元已成功編譯。因其中幾條字串也出現在別的腳本，實際覆蓋 45 個出現位置、
5 個目標區塊（`GPL-6`、`GPL-9`、`GPL-162`、`GPL-195`、`GPLI-1`）：

```text
scratch_test/gpl6_balkazar_zh_v1
GPLDATA.GFF sha256:
17cbb91fc8029dde2ccebbc804dcf97b1d2f3ccb83588fda6a38b03f8098f2d3
```

驗證結果：

- 38 個唯一翻譯單元；
- 45 個已修補出現位置；
- 1,078 個非目標區塊保持不變；
- GPLI-1 的外部事件入口已隨 GPL 位移重定位。

此工作包以乾淨英文版為來源，尚未與 v26/v27 的 GPL-2～5、NAME-1、GPLI-1 組合，也未經
使用者實機測試；它不是新的正式 checkpoint。

## 4. 字庫與測試

本輪 inventory 以完整 `localization_manifest.csv` 為來源，append-only mapping 從 1,276 筆
增為 1,314 筆，其中 1,312 個字元目前有效。新字庫：

```text
scratch_test/formal_cjk_fusion_10x10_v18_gpl6
mapping fingerprint:
aac8a7c87eaf5da420418413486a9adf560500794045ae6c8ad588ac52914c4f
```

共 6 banks，`verify-banks` 已通過 1,312 個有效字形。標準函式庫測試結果：

```text
python -m unittest discover -s tests -p "test_*.py" -v
Ran 44 tests
OK
```

環境未安裝 `pytest`，但不影響上述 `unittest` 測試集執行。

## 5. 下一步

維持翻譯優先。可接續選擇下一個情節完整的 GPL 批次；若要建立可玩 staging，必須先把
本輪安全 GPL 補丁與既有 v26/v27 組合包合併，不能以本輪獨立 `GPLDATA.GFF` 取代正式
checkpoint。
