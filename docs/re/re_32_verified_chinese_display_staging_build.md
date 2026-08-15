# 中文顯示完整 staging build 與啟動 checkpoint

> **2026-08-15 更新：**本頁的 v1 是歷史 checkpoint。現行可玩基準為 9-row v5：
> scratch cache 已縮至 `36AA:545A..5533`，EBOX 也能以完整三-byte Base94 token
> 換行；法術說明的執行期證明見
> `re_35_relocation_safe_ebox_base94_wrap_and_spell_runtime_proof.md`。

> **同日版面更新：**v6 在不改動翻譯原文的前提下，於法術名稱冒號後插入 CRLF；
> 實機已確認名稱與說明分段顯示正常。現行基準改為
> `scratch_test/cjk_display_staging_9row_v6_title_newline`，詳見
> `re_36_spin_title_description_hard_break_runtime_proof.md`。

> 日期：2026-08-15  
> 前置：`re_29_cjb1_direct_read_cross_bank_runtime_proof.md`、`re_31_spin_gff_transport_importer_and_roundtrip.md`  
> 狀態修正：本文件的 15-row staging 結構驗證雖通過，但實機發現不可接受的文本缺漏；在分頁與 layout 尚未修正前，不作為目前的可玩基底。15-row 方案仍保留為後續研究方向。修正見 `re_33_global_font_height_text_loss_and_9row_recovery.md`

## 1. 為何需要新的 staging builder

先前 runtime probe 雖已證明中文 renderer 與跨 bank direct-read，但其 FONT 曾把
`@#$[]*` 等 ASCII 測試槽換成中文字。該資源適合 probe，不適合一般遊戲。

`tools/build_cjk_display_staging.py` 改由乾淨 `RESOURCE.GFF/FONT-100` 建立正式測試基底：

1. 保留原本 256 個 character-map identity 與全部 ASCII glyph；
2. 將全域高度由 9 rows 置中 padding 至 15 rows；
3. 不替換任何 ASCII glyph；
4. 將 payload 補至已實機證明的 scratch offset `0x3640`；
5. 附加一筆 242-byte scratch record，供 runtime cache 覆寫。

乾淨來源 FONT 為 8,299 bytes，輸出 FONT 為 14,130 bytes：

```text
15-row legacy records + alignment padding  13,888 bytes (0x3640)
scratch record                                 242 bytes
total                                       14,130 bytes
```

## 2. Builder 輸入與安全邊界

```powershell
python tools/build_cjk_display_staging.py `
  --bank-package scratch_test\formal_cjk_pixel_aligned\cjk-bank-set.json `
  --spin-package scratch_test\spin_gff_import\gff-text-replacements.json `
  --output scratch_test\cjk_display_staging_v1
```

Builder：

- 要求輸出目錄尚不存在；
- 在暫存目錄完成全部工作與驗證後才移到正式輸出；
- 永不修改 Steam 原始目錄；
- 拒絕 mapping fingerprint 不符或 bank SHA-256 不符；
- 從乾淨 `DSUN.EXE` 產生 resident scratch-cache patch；
- 複製完整原廠 `GAME/DARKSUN`，並加入 `C0.BIN`～`C3.BIN`；
- 套用 172 個 SPIN replacements 與新的 FONT-100；
- 逐 chunk 抽回最終 RESOURCE 驗證；
- 逐檔確認其他複製的遊戲檔未改變；
- 產生 `build-manifest.json` 與 `launch-dosbox-x.cmd`。

## 3. 本次 build 結果

```text
patched DSUN.EXE SHA-256
10c38ab1b9fd4fe8e03d88c56ac7275c29f213271955d988e27236e028b90723

patched RESOURCE.GFF SHA-256
b0c44aa6f9d77ac392065594c87ce2d005dfaea7e0b74ba77951225ab06eb329

FONT-100 SHA-256
bb79355529dc03466a50cf91ee5ad184235db8cbc5dc8760760bb34146672090
```

RESOURCE 全量驗證：

```text
all chunks                   1205
target chunks                 173  (172 SPIN + FONT-100)
changed target chunks         173
unchanged non-target chunks  1031
allowed metadata change         1  (GFFI-1)
```

另外 57 個原廠遊戲檔逐檔與來源相同。四個 bank 均通過 CJB1 結構、長度與
SHA-256 驗證，涵蓋 mapping 中 881 個 active glyph。

## 4. 正確啟動方式

輸出保留原廠目錄布局：

```text
cjk_display_staging_v1/
  base.conf
  graphics.conf
  game.conf
  launch-dosbox-x.cmd
  build-manifest.json
  GAME/DARKSUN/
    DARKSUN.BAT
    DSUN.EXE
    RESOURCE.GFF
    C0.BIN ... C3.BIN
    ...其餘原廠檔案
```

Launcher 在 staging root 作為工作目錄，載入原廠三份 conf。`game.conf` 執行：

```text
mount c .\GAME
c:
cd DARKSUN
call DARKSUN.BAT
```

關鍵設定仍是 `cycles=fixed 7000`，且必須由 `DARKSUN.BAT` 進入，不能直接執行
`DSUN.EXE`。

本輪啟動後的後續實機結果推翻「可玩」判定：開場原本同框四行被切成兩行，畫面雖
顯示 `MORE`，但點擊後無法進入下一頁，後兩行文本不可達。原因與修正範圍記錄於
re_33；本文件保留作 builder 結構與負面實驗紀錄。

## 5. 測試狀態與下一 checkpoint

自動測試目前 19 項通過，新增覆蓋：

- clean FONT 的 256-glyph identity 保存；
- 9→15 row conversion；
- 固定 `0x3640` scratch boundary；
- 242-byte scratch record 長度拒絕規則；
- patched EXE 回讀驗證；
- 173 個 RESOURCE target 與所有 non-target chunk 比對。

下一 checkpoint 是在此 staging 中進入法術說明畫面，確認至少一筆中文 SPIN：

1. 中文 glyph 正確顯示；
2. ASCII 數字與標點未被測試 glyph 汙染；
3. 長句換行不截斷；
4. 離開再進入後重畫正常；
5. 多個 bank 的字可在同一說明中切換且不當機。
