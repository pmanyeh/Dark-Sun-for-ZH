# SPIN 法術名稱／說明硬換行實機證明

> 日期：2026-08-15  
> 前置：`re_35_relocation_safe_ebox_base94_wrap_and_spell_runtime_proof.md`  
> 現行基準：`scratch_test/cjk_display_staging_9row_v6_title_newline`

## 1. 目標與結果

法術名稱不再與說明接續於同一行。以 BLESS 為例，canonical 翻譯仍是：

```text
祝福術：使友方角色的 THAC0 提升 1 點。效果不可疊加。適合在戰鬥前施放。
```

送入遊戲的 display payload 則是：

```text
祝福術：<CR><LF>使友方角色的 THAC0 提升 1 點。效果不可疊加。適合在戰鬥前施放。
```

2026-08-15 實機畫面確認：

- `祝福術：` 單獨顯示為名稱區塊；
- 說明從下一個文字區塊開始；
- 後續自動換行正常；
- 中文與 `THAC0`、數字混排正常；
- 無 `^xy` 尾碼外漏、缺字或閃退。

使用者對此版面結果確認為「完美」。

## 2. 實作政策

`compile-gff-text` 新增明確的 `--title-newline` 選項。啟用時只在 SPIN 翻譯的
第一個全形 `：` 或半形 `:` 後插入 CRLF，並移除說明開頭的 ASCII spaces。

這是輸出階段的 display policy，不會把 CRLF 寫回翻譯 catalog。因此：

- 翻譯資料仍適合搜尋、校對與輸出其他格式；
- 不適合此排版的 UI 可以停用選項；
- package manifest 會記錄是否啟用，build 可重現而非依賴人工修改。

編譯命令：

```powershell
python tools/cjk_localization_pipeline.py compile-gff-text `
  --title-newline `
  --output scratch_test\spin_gff_import_title_newline
```

## 3. 全集驗證

```text
SPIN replacement chunks       172
title_newline=true records    172
title_newline=false records     0
RESOURCE target chunks        173  (172 SPIN + FONT-100)
RESOURCE unchanged chunks    1031
automated tests                18 passed
```

BLESS（SPIN 70）與 ENTANGLE（SPIN 74）的第一個 CRLF 都位於 12-byte encoded
title 後；換行沒有切進三-byte Base94 token。

## 4. Build 身分

```text
patched DSUN.EXE SHA-256
d602eb1acf5b9df8fbc643ce23355d585d3450ba6b5f7d39c8b228cd83b1fd4a

patched RESOURCE.GFF SHA-256
ebd85c1b0a8fcb0c3f48f16dcfa53f141f06140eaf634ebdf79e58eb7161227f

mapping fingerprint
49578a66bf5b6294aa5de7c47d226cb7d6967f7ede31d56ae977a67d41079ba3
```

EXE 與 v5 相同；v6 的差異只在經驗證的 SPIN display payload。v5 保留為沒有標題
硬換行的回退版本。
