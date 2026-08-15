# SPIN GFF 傳輸匯入器與全 chunk 回讀證明

> 日期：2026-08-15  
> 前置：`re_30_eten_16x15_replaceable_glyph_source_pipeline.md`  
> 結論：現有 SPIN 翻譯已能安全編碼、重封裝至獨立 `RESOURCE.GFF`，並經全檔逐 chunk 回讀驗證

## 1. 本階段範圍

現有 466 筆非空翻譯分成兩種資源形態：

- 170 個 SPIN 翻譯單元，展開為 172 個完整 `RESOURCE.GFF/SPIN` chunk；
- 296 個 NAME 翻譯單元，位於 `GPLDATA.GFF/NAME-1` 的結構化記錄內。

SPIN 是獨立文字 chunk，可以由 GFF 容器重排安全地改變長度。NAME 含有
`record_id` 與 `chunk_offset`，改變字串長度會牽動後續記錄；因此本階段明確略過
NAME，不把「base-94 可編碼」誤判成「可直接覆寫」。

## 2. 可重複的編譯命令

```powershell
python tools/cjk_localization_pipeline.py compile-gff-text `
  --output scratch_test\spin_gff_import
```

編譯器會：

1. 從 `localization_manifest.json` 精確展開每個 SPIN location；
2. 以 append-only `cjk_mapping.json` 將中文轉成 runtime-proven base-94 triple；
3. 驗證 catalog 的原文 ASCII byte 長度與 chunk 長度；
4. 依 location 保留 terminator，而不是統一補換行；
5. 寫出 `RESOURCE.GFF/SPIN-<id>.txt` 與具 SHA-256 的 replacement manifest；
6. 拒絕 embedded location、錯誤 kind、衝突 payload、未映射字元及保留字元 `^`。

真實 catalog 結果：

```text
replacement_chunks=172
replacement_locations=172
terminator_CRLF=170
terminator_none=2
skipped_translated_units=name:296
```

無 terminator 的兩個原始 chunk 是 SPIN 92 與 125；匯入器保留其原始形態。

## 3. 重封裝與全檔驗證

```powershell
python tools/cjk_localization_pipeline.py pack-gff-text `
  --package scratch_test\spin_gff_import\gff-text-replacements.json `
  --output scratch_test\spin_gff_verified_build\RESOURCE.GFF
```

此命令呼叫 repository 內的 `gff-cat`：

```text
pack-text source RESOURCE.GFF + replacement directory
  -> isolated output RESOURCE.GFF
extract --all source
extract --all output
  -> inventory equality
  -> target length + SHA-256 equality
  -> every non-target payload byte equality
```

原始遊戲檔與輸出檔不得是同一路徑，原始 Steam 安裝不會被覆寫。

## 4. 實測結果

來源：

```text
bytes   3,422,240
sha256  85d0afe53d40f6f1fa0285041531aeee153f170088826a87d1d3b976b5716179
```

輸出：

```text
bytes   3,425,845
sha256  1d12194efd6f6641fe8978f7ca2468bd40cabcf5fed819ad84a23d921153e2f5
```

全 chunk 回讀比較：

```text
all_chunks                    1205
target_chunks                  172
changed_target_chunks          172
unchanged_non_target_chunks   1032
allowed_container_metadata       1  (GFFI-1)
```

`GFFI-1` 是包含 chunk 長度與位址的容器索引；可變長 SPIN 重封裝後必然更新。
除了這個索引與指定的 172 個 SPIN 外，其餘資源 payload 全部逐 byte 相同。

驗證紀錄寫至：

```text
scratch_test\spin_gff_verified_build\RESOURCE.GFF.verification.json
```

## 5. 自動測試

目前 `python -m unittest discover -s tests -v` 共 17 項通過。新增覆蓋包含：

- 多 location SPIN 展開；
- base-94 payload 與 CRLF 保存；
- embedded SPIN location 拒絕；
- 目標 SHA-256 驗證；
- 非目標 chunk 不變；
- `GFFI-1` metadata 更新白名單。

## 6. 下一個 checkpoint

SPIN 封裝路徑已閉環。下一個獨立問題是解析並重建
`GPLDATA.GFF/NAME-1` 的記錄表，使 296 個 NAME 可以變長而不破壞記錄邊界；
在該結構獲得 parser/rebuilder 與 round-trip 證明前，不應直接覆寫 NAME 字串。
