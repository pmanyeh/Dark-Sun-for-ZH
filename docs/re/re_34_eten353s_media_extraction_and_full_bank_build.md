# ETEN 3.53S 媒體辨識、字庫抽出與完整 bank build

> 日期：2026-08-15  
> 前置：`re_30_eten_16x15_replaceable_glyph_source_pipeline.md`、`re_33_global_font_height_text_loss_and_9row_recovery.md`  
> 結論：使用者提供的目錄內確實包含 ETEN 3.53S 安裝媒體；正式 16×15 bitmap 已抽出並涵蓋目前全部 881 字

## 1. 檔名與內容錯位

`Fonts/` 中多個檔案的外部名稱不代表實際內容：

- `stdfont.15` 實際是載入 `seal24.bin` 的 UTF-8 C 原始碼，只有 4,725 bytes；
- `usrfont.15m` 實際是 UEFI `main.c` 原始碼；
- `eten.h` 是 3,840-byte bitmap，尺寸剛好等於 256×15，實際對應 ASCFONT；
- `ascfont.15` 的 sfnt name 是 `Chong Xi Small Seal`，實際為輪廓字型；
- `font.c` 是 18,896,896-byte ISO9660 image，而不是 C source。

因此 pipeline 不依檔名猜測，先檢查 binary magic、容量與 archive 目錄。

## 2. ISO 識別

`font.c` 在 sector 16 具有 ISO9660 primary volume descriptor：

```text
magic         CD001
volume label  ETEN353S
```

archive 內含：

```text
DISKS/DISK1 ... DISKS/DISK7
FILES/STDFONT.15
FILES/SPCFONT.15
FILES/ASCFONT.15
FILES/ET16*.COM
FILES/ETSETUP.EXE
...
```

實際抽出命令只取三個字庫，不展開整套媒體：

```powershell
New-Item -ItemType Directory scratch_test\eten353_extracted
tar -xf Fonts\font.c `
  -C scratch_test\eten353_extracted `
  FILES/STDFONT.15 FILES/SPCFONT.15 FILES/ASCFONT.15
```

抽出位置受 `.gitignore` 保護；`Fonts/` 也整體忽略，避免專有媒體被意外提交。

## 3. 原始字庫驗證

```text
ASCFONT.15      3,840 bytes
SHA-256 1d0cf09d0a319a9e7039190688c6a905ba4370bd369fbfcfa43b2078480d6918

SPCFONT.15     12,240 bytes = 408 glyphs × 30
SHA-256 f32049ba2a7a21db908878a488a2c1d93c389d17398cf46db1390ba89e247605

STDFONT.15    392,820 bytes = 13,094 glyphs × 30
SHA-256 39ba9c8519d75fe11d5988a8a27e6daa5794ad2ea215108390b0d7e9e53ff701
```

容量與 ETEN 3.53 16×15 contract 完全相符。

## 4. Mapping coverage

```powershell
python tools/cjk_localization_pipeline.py audit-eten
```

結果：

```text
active_glyphs  881
eten_std       872
eten_spc         9
eten_missing     0
```

目前翻譯語料所需的 881 字全數能從使用者提供的 ETEN media 取得，不需要 TTF
fallback 或 synthetic glyph。

## 5. 正式 16×15 CJB1 banks

```powershell
python tools/cjk_localization_pipeline.py build-banks `
  --eten-dir scratch_test\eten353_extracted\FILES `
  --output scratch_test\formal_cjk_eten353_16x15

python tools/cjk_localization_pipeline.py verify-banks `
  --package scratch_test\formal_cjk_eten353_16x15\cjk-bank-set.json
```

結果：

```text
bank 0  256 glyphs  62,992 bytes  a23604e0662163d3e912bd857bc5972d9a7addad5b888e8d7c5f5b56753d4959
bank 1  256 glyphs  62,992 bytes  4df2f90c54a1c78c501b3cde4520ff020da52b96bb9127e3dd5cc3d34e2517e6
bank 2  256 glyphs  62,992 bytes  2f139c56e41691569126e975e5158285ae83541134737047eadc249e15a86349
bank 3  113 glyphs  27,814 bytes  e45e4dcaa865442a63030da802a3edf549dad9bbd0dc76bab6474e8a034ebbb6
```

`verify-banks` 通過：

```text
verified_banks       4
verified_glyphs    881
max_record_bytes   242
```

## 6. 與 9-row recovery 的關係

這次完成的是「真正倚天 16×15 glyph source」與 CJB1 bank build，不代表直接將
全域 FONT 改回 15-row。`re_33` 已證明未修改 paginator 的全域 15-row layout 會在
GPL 多指令組句造成文本缺漏。

兩條線並行保留：

```text
目前可玩線  Fusion Pixel 10×9 + 原生 9-row layout
精進研究線  ETEN 3.53S 16×15 + paginator/layout 修正
```

下一個 16×15 checkpoint 應先修正或解耦 layout，再使用本文件生成的正式 ETEN
banks 做 A/B；不再以 Noto provisional glyph 判斷最終字形品質。
