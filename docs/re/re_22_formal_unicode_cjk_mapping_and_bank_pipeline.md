# 正式 Unicode→CJK ID 與字模 bank 管線

> 日期：2026-08-14  
> 前置文件：`re_21_cross_255_cjk_id_multibank_proof.md`

## 1. 結論

Renderer 原型已轉入可重現的資料管線。此處「正式」指穩定的 Unicode ID、transport
與 bank 格式；目前由 Noto Sans TC 產生的 glyph bitmap 只是暫用測試資產，不是預定
採用的倚天 16×15 正式字形。`tools/cjk_localization_pipeline.py` 現可：

1. 從 UTF-8 CSV 的 `translation_zh_tw` 欄位建立 Unicode 字元 inventory。
2. 維護 append-only 的 `localization/cjk_mapping.json`。
3. 為每個字元固定 u16 CJK ID、bank、index 與 printable triple。
4. 以繁中字型 rasterize 16x15 palette glyph。
5. 輸出各自小於 64 KiB、具 u16 相對 record offsets 的獨立 bank。
6. 在真正封裝前拒絕未映射字元與 transport 容量溢位。

## 2. 第一批正式 inventory

目前主要對話 worksheet 尚無中文；綜合 localization manifest 已有 466 筆非空譯文：

| 類別 | 筆數 |
|---|---:|
| `name` | 296 |
| `spin` | 170 |

NFC 正規化後共有 881 個需要新增 glyph 的可見非 ASCII 字元。ASCII 與空白仍沿用
遊戲原字型／控制流程，不占 CJK ID。第一次建立時依 Unicode code point 排序；後續只會
把新字元接在尾端，既有 ID 永不重新編號。

```text
mapping format   darksun-cjk-map v1
active glyphs    881
CJK IDs          0..880
banks             4
bank capacity     256 IDs
```

## 3. 為何不再附加到單一 FONT segment

16x15 glyph 使用 16-byte advance，每筆 record 為：

```text
u16 width + 16 * 15 palette bytes = 242 bytes
```

881 筆約需 213 KiB，已遠超目前 FONT runtime pointer 的單一 64 KiB segment。先前
CJK2 跨 bank 測試只放六筆稀疏 glyph，證明了 ID 與 bank selection，並未消除 segment
容量限制。因此正式輸出改為獨立 bank set，下一階段再讓 resident loader／renderer
以 far-bank 或 glyph scratch cache 取用。

## 4. CJB1 bank 格式

每個 `cjk-bank-NNN.bin` 均可單獨定位，且檔案與 record offset 都不超過 u16：

```text
header <4sHHHHI>
  magic             "CJB1"
  version           1
  bank_id           u16
  glyph_height      u16
  glyph_count       u16
  directory_offset  u32

directory[glyph_count] <HH>
  index_in_bank     u16
  record_offset     u16

record
  width             u16
  pixels            width * glyph_height bytes
```

以暫用的 `NotoSansTC-VF.ttf`、15-pixel bitmap、16-pixel advance 建置結果：

| Bank | Glyphs | Bytes | SHA-256 |
|---:|---:|---:|---|
| 0 | 256 | 62,992 | `5504f5a14b0f22128b889699f24fefdd9390926133eab4e8b3c65db04ad00bc5` |
| 1 | 256 | 62,992 | `8a4f9cffb8651f6eb210b1ec60222725ca55f3b7e825ccc24cd01f8f2a296aef` |
| 2 | 256 | 62,992 | `449f149e59d8c7a43779712faf383b4969a83c1df7536ae0c12480ebd82b1eaf` |
| 3 | 113 | 27,814 | `126f8bc90b0a4fcf28f062ba3916ef1579634735df9813d1f9a41598b90478a5` |

上述 SHA-256 只用於驗證 CJB1 pipeline 與 runtime loader，不應視為最終發行字庫。
預定字源是使用者合法自備的倚天 `STDFONT.15` 加 `SPCFONT.15`；專案不散布這兩個
商業字庫檔。

## 5. Printable-triple transport（已由 re_23 驗證）

第一版 control-byte pair 候選在實機上被 renderer 上游吃掉，已正式否決。替代格式為：

```text
CJK glyph = '^' + base94 digit + base94 digit
digit range = '!'..'~'
capacity = 94 * 94 - 1 = 8,835 IDs
literal '^' = forbidden
reserved sequence = '^^^' / ID 5795
```

完整 catalog 的原始字串沒有任何 `^`，因此不會與尚未重新編碼的英文碰撞。re_23 已用
12 組 boundary triples 實機驗證 0、255、256、880、881 與最高 ID 8835；完整畫面
成功顯示「中文顯示成功中文顯示成功」。re_24 已進一步以零對照表的 base-94
algorithmic resolver 重複通過同一組邊界與換行測試。

## 6. 驗證

```text
python -m unittest tests.test_cjk_localization_pipeline
Ran 4 tests ... OK
```

測試涵蓋 inventory 過濾、append-only ID、triple 唯一性／printable bytes，以及 CJB1 u16
record directory。四個實際 bank 亦全部成功產生，最大檔案為 62,992 bytes。

## 7. 下一個實機 checkpoint

Printable triple 與 algorithmic resolver 均已完成。接下來：

1. 驗證 `%`、TAB、換行與一般 ASCII 混排保持原語意。
2. 將正式 UTF-8 translation importer 接上 printable-triple encoder。
3. 實作 far-bank loader 或單 glyph scratch cache。
