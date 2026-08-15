# 倚天 16×15 可替換字源管線

> 日期：2026-08-15  
> 前置文件：`re_29_cjb1_direct_read_cross_bank_runtime_proof.md`  
> 狀態：程式與 coverage 完成；等待使用者合法自備字庫作真實資料建置

## 1. 結論

Unicode mapping、base-94 transport、CJB1 banks 與 runtime direct-read cache 現已和
glyph source 解耦。`tools/cjk_localization_pipeline.py` 支援原生倚天 3.53：

```text
STDFONT.15 + SPCFONT.15
  -> Unicode encode Big5
  -> ETEN partition/slot
  -> native 16x15 MSB-first bitmap
  -> Dark Sun palette record
  -> unchanged CJB1 banks
```

日後取得合法字庫時不需重新分配 CJK ID、不需重新編碼翻譯，也不需修改 EXE。

## 2. 字庫格式與分區

```text
STDFONT.15  13,094 glyphs × 30 bytes  漢字
SPCFONT.15     408 glyphs × 30 bytes  全形符號
glyph          16 × 15 pixels
row             2 bytes, MSB at left
```

Big5 分區規則與 `D:\git\u5-cht\tools\build_eten_font.py` 一致：

- `A140..A3BF` -> `SPCFONT.15`；
- `A440..C67E` -> `STDFONT.15` 常用字；
- `C940` 起 -> `STDFONT.15` 次常用字；
- 明確拒絕 Big5 空隙與超出字庫的 code。

oracle：

```text
。 A143 -> spc slot 3
一 A440 -> std slot 0
中 A4A4 -> std slot 66
```

## 3. 目前翻譯 coverage

不需要實際字庫檔即可執行：

```powershell
python tools/cjk_localization_pipeline.py audit-eten
```

目前 append-only mapping 結果：

```text
active_glyphs  881
eten_std       872
eten_spc         9
eten_missing     0
```

因此目前全部中文字與全形標點均有倚天原生 slot，不需混用 TTF fallback。

## 4. 正式建置命令

使用者將合法自備的兩個檔案放在同一個本機目錄後：

```powershell
python tools/cjk_localization_pipeline.py build-banks `
  --eten-dir D:\path\to\legal-eten-fonts `
  --output scratch_test\formal_cjk_eten

python tools/cjk_localization_pipeline.py verify-banks `
  --package scratch_test\formal_cjk_eten\cjk-bank-set.json
```

預設會套用 Dark Sun palette `0xFE` 前景與 `0x14` 右下陰影；可用 `--no-shadow`
建立無陰影 A/B 版本。`cjk-bank-set.json` 會記錄兩個來源檔各自 SHA-256，但不複製或
散布原商業字庫。

## 5. 測試與 fallback 邊界

自動測試增至 14 項，新增內容包含：

- Big5/ETEN partition oracle；
- 合成 STDFONT/SPCFONT fixture 的原生 bit extraction；
- 固定 16-pixel advance、240 pixel bytes 與 242-byte record；
- TTF provisional build 的 CLI regression。

TTF 模式仍保留作沒有倚天檔時的 loader 測試，但 package 會標記
`glyph_source.kind = ttf-provisional`。倚天模式則標記 `eten-3.53-16x15`，兩者不再
混稱為同一種正式字形。

## 6. 取得字庫後的 checkpoint

1. 跑 `audit-eten` 與兩個真實字庫的 size/oracle 驗證。
2. 建立有陰影與 `--no-shadow` 兩套四-bank package。
3. 先以 ID 255/256「徒得」比較原生倚天可讀性。
4. 再測「中文顯示成功」、九個全形標點、長句、MORE 與回頁。
5. 固定選定版本的 source SHA-256 與四個 bank SHA-256，作為發行 build provenance。
