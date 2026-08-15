# UTF-8 catalog transport compiler

> 日期：2026-08-14  
> 前置文件：`re_24_algorithmic_base94_resolver_runtime_proof.md`

## 1. 結論

正式 UTF-8 翻譯表現已接到 runtime-proven printable-triple transport。新增命令：

```powershell
python tools/cjk_localization_pipeline.py compile-catalog `
  --output scratch_test\encoded_catalog.json
```

它讀取 `localization/catalog/localization_manifest.csv` 的 `translation_zh_tw`，依
`localization/cjk_mapping.json` 將每個非 ASCII 字轉成 `^` 加兩個 base-94 digits，
並輸出可稽核的 encoded catalog package。

對目前 catalog 實跑結果：

```text
encoded_units=466
mapping entries=881
errors=0
```

因此現有 466 筆非空翻譯使用的所有中文字均已登錄，且都能轉成 renderer resolver
接受的 printable bytes。

## 2. 輸入安全規則

`encode_text()` 先作 NFC normalization，再逐字處理：

- ASCII（包括 `%` 格式參數、TAB、CR/LF）原 byte 保留。
- 非 ASCII 可見字必須存在 append-only mapping。
- literal `^` 一律拒絕，避免和 CJK prefix 混淆。
- NUL 一律拒絕，避免翻譯在資源字串中提早終止。
- 未登錄 Unicode 字元一律拒絕，不作靜默 replacement。

錯誤訊息包含 CSV 路徑、列號、unit ID、字元與 Unicode code point；整批掃描後才
失敗，最多一次列出前 20 筆，方便翻譯表校正。

## 3. 輸出格式

JSON package 記錄：

- catalog 與 mapping 的 SHA-256；
- 欄位名稱與編譯 unit 數；
- 每筆 unit ID、原 UTF-8 翻譯、encoded ASCII、Base64 與 byte length。

`encoded_ascii` 方便人工比對；`encoded_base64` 可無歧義保存 TAB／換行等控制 byte。
package 仍是中間產物，尚未直接回填 GPL/GFF。

## 4. 自動測試

`tests/test_cjk_localization_pipeline.py` 現有六項測試全部通過。新增案例明確驗證：

```text
中%S<TAB>文<LF>
 -> ^#d%S<TAB>^#e<LF>
```

其中 ID 255／256 跨越第一個 256-glyph bank 邊界；同時測試 literal `^`、NUL 與
未登錄中文字皆被拒絕。

## 5. 下一步

Importer 已能產生完整 runtime bytes，接下來的核心阻塞仍是 renderer 端的正式
881 字載入：實作跨 segment far-bank loader 或 single-glyph scratch cache。完成後，
可將 encoded package 接到 GPL/GFF replacement，做 `%` 參數、長句、MORE 與回頁的
整合實機驗證。
