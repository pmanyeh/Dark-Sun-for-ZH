# NAME-1 固定記錄匯入器與物品面板繪製路徑缺口

> 日期：2026-08-15
> 延續：`re_40_v15_spell_and_dialogue_ui_regression_confirmation.md`

## 1. 目標

依交接備忘錄第 12.5 步「擴大正式文本翻譯」，優先匯入已在
`localization/NAME_objects_translated.json` 完成翻譯、但從未接入 runtime 的
296 筆裝備／物件名稱（`GPLDATA.GFF/NAME-1`）。`re_31` 曾記錄此表為「含
`record_id` 與 `chunk_offset` 的結構化記錄」，因改變字串長度會牽動後續記錄，
故明確擱置未做匯入器。

## 2. NAME-1 真實二進位結構

實際位元組層級分析推翻了先前的假設：`NAME-1` chunk 共 8,050 bytes，
`8050 / 25 = 322`，且逐一切成 25-byte 區塊後，321 筆均能乾淨解出一個
NUL-terminated 的可印 ASCII 名稱，僅 1 筆（slot 149）整筆為 0（未使用的
空白記錄）。因此 `NAME-1` 是**固定寬度 25-byte × 322 筆**的記錄表，不是變長
記錄：

```text
container   GPLDATA.GFF
kind        NAME
chunk_id    1
record size 25 bytes
records     322（321 個名稱 + 1 個空白 slot 149）
field       NUL-terminated ASCII 名稱；terminator 之後的位元組是未清空的
            殘留 buffer 內容（常見到重複出現的殘留片段如
            `...\NAMEIX\*.oda`），執行期不會讀取，匯入時原樣保留
```

因為每筆記錄寬度固定，翻譯只要「編碼後長度 + 1（NUL）≤ 25 bytes」即可直接
**原地覆寫**，完全不需要像 SPIN／GPL 那樣做長度重定位——這比先前任何一個
匯入器都更單純。

## 3. 舊 328 筆目錄的資料品質問題

先前 `NAME_objects_translated.json`／`localization_manifest` 的 328 筆
`name` 項目是用「正則掃描 NUL 分隔字串」萃取的，不是照真實記錄邊界切的。
比對後發現：

- 253 筆與真實記錄完整字串完全相符，可直接沿用其翻譯；
- 68 筆真實記錄的完整名稱被錯誤切成兩段以上目錄項，例如真實記錄
  `"Trail of Blood"` 被切成獨立的 `"Trail"` 與 `"Blood"`；
  `"Two-handed Sword"` 被切成 `"Two"` 與 `"Sword"`；
  `"Wand of Missiles"` 被切成 `"Wand"` 與 `"Missiles"`；
- 對應地，舊目錄中有 51 筆是這類破碎片段，不對應任何真實記錄，本次予以移除。

本次已將這 68 筆（67 個不同英文原文）重新以完整片語翻譯，並重建
`localization/NAME_objects_translated.json`（`id` 欄位改為真實 0-based slot
編號，`count` 改為 321），以及同步 `localization/catalog/localization_manifest.csv`
／`.json` 的 `name` 類別（296 → 321 筆，`README.md` 對應數字已更新）。

## 4. `cjk_mapping.json` 作用中字元回歸

第一次呼叫 `update_mapping()` 時誤用只涵蓋本次 NAME 翻譯的 inventory，
導致舊有 901 個字元的 `active` 旗標被整批覆寫（許多 SPIN／GPL 對話用到的
字元被誤標為非作用中）。已用 v15 既有 bank set（`cjk-bank-000..003.bin`）
反推出原本 901 個作用中 CJK ID，與本次新 inventory 取聯集後修正，
最終 923 個字元全數作用中（901 舊 + 22 新）。重建的 4 個 bank 中，
前 3 個與 v15 原始 bank SHA-256 完全一致，第 4 個為嚴格附加（133→155 筆）。

## 5. NAME-1 匯入器：`tools/compile_gff_name_records.py`

新工具直接解析／重寫固定寬度記錄，不做任何 chunk 長度或位移調整：

1. 用 `gff-cat extract` 取出 `NAME-1` 原始 8,050 bytes；
2. 依 25-byte 切成 322 筆，逐筆解出英文名稱；
3. 對照 `NAME_objects_translated.json`，找到翻譯就用 `encode_text()`
   轉成 Base94 triple，驗證 `len(encoded)+1 <= 25`，組成
   `encoded + NUL + 原尾端殘留 bytes`；找不到翻譯或本身是空白記錄則整筆
   原樣保留；
4. 用 `gff-cat replace` 寫回；
5. 用既有 `verify_extracted_gff_chunks()` 對整個 `GPLDATA.GFF`
   （1,084 chunks）做全容器驗證，只允許 `NAME-1` 與 `GFFI-8`
   （容器索引）改變。

工具支援 `--prior-package` 疊加在既有的 `darksun-gpl-dialogue-patch` 封裝
之上（例如疊加在 `re_37` 的 Celgor GPL 對話 patch 上），輸出格式相容的
組合封裝，因此 `tools/build_cjk_display_staging.py` 完全不需要修改，
仍用既有 `--gpl-package` 參數即可載入。

```powershell
python tools/compile_gff_name_records.py `
  --prior-package scratch_test/gpl_celgor_zh_v1/gpl-dialogue-patch.json `
  --translations localization/NAME_objects_translated.json `
  --mapping localization/cjk_mapping.json `
  --output scratch_test/gpl_celgor_name_v1
```

驗證結果：`all_chunks=1084`、`target_chunks=2`（`GPL-2` + `NAME-1`）、
`changed_target_chunks=2`、`unchanged_non_target_chunks=1081`、
`name_records_translated=321`。新增 6 項 unit test
（`tests/test_gff_name_records_importer.py`）覆蓋固定記錄解析、原地覆寫、
殘留位元組保留、與長度超限拒絕；完整測試套件 35 項全數通過。

## 6. v16 staging 與實機結果：物品面板顯示亂碼

```text
scratch_test/cjk_display_staging_v16_name_records
```

沿用 v15 已確認的 9-row layout／10-row CJK draw／EBOX line-gap 2／視窗 2×，
疊加上述 NAME-1 patch 與含新字元的 bank set。`patched_exe_sha256`／
`patched_resource_sha256` 與 v15 完全相同（NAME-1 只動 `GPLDATA.GFF`）。

實機測試：翻譯後的位元組**確實正確寫入**（記憶體內可讀到完整
`^$3^&k^'>` 等 Base94 triple），但物品說明彈窗、右側裝備欄、底部物品列
全部把這些 triple 當成單一 ASCII 位元組逐字畫出來，顯示為
`V⁄%V&5V"0` 這類亂碼，而不是解析成中文字。

## 7. 即時除錯：排除已知 renderer

本次發現 `D:\git\DOSBox-X-AI` 是一個實驗性 MCP／原生橋接除錯器專案
（`pmanyeh/dosbox-x` fork，`ai-mcp-bridge` 分支），監聽
`127.0.0.1:9876`，可用 `ai/dosbox_client.py` 的 `DOSBoxClient` 直接以
newline-delimited JSON 對原生 DOSBox-X 除錯器下中斷點、讀記憶體、
反組譯、單步執行，不需要透過 MCP 工具註冊即可用一般 Python script 呼叫。
目前一直在用的 `dosbox-x.exe` 本身就是這個帶橋接層的 build，埠口預設
就在監聽。

用這個橋接層做了以下即時排查：

1. 在共用 glyph 繪製入口 `36AA:06C0` 下中斷點，逐字元記錄實際命中的
   `AL`：連續數十次命中都是畫面上其他 UI 文字（角色名、按鈕、數值），
   從未出現 Base94 prefix byte `0x5E`（`^`），顯示物品面板文字並未經過
   `36AA:0941`／`36AA:094A`（已 patch 的 resolver hook）這條路徑；
2. 在整個 EXE 中搜尋另一個「讀一個 byte」特徵位元組序列 `26 8A 07`
   （`mov al,es:[bx]`），扣掉已知 3 個 patch 點與 1 個已確認屬於
   FONT-100 payload 掃描（`36AA:078E`）的位置後，在 segment `36AA`
   內還有 10 個候選位址；全部同時下中斷點並請使用者重新觸發物品面板
   重繪，**全數未命中**；
3. 搜尋 live 記憶體找到目前顯示中的翻譯字串（如「投石索」的編碼
   `^$3^&k^'>`）實際位址：物理位址 `0x78E74`（`7800:0E74`），確認
   `NAME-1` 表格是整份原封不動載入到這裡；
4. 在該位址設寫入變化監看點（`breakpoint.memory.set`，`BPPM`），來回切換
   法術／物品畫面觸發多次重繪，**從未觸發**——證明該緩衝區是唯讀重複
   讀取，執行期沒有另外複製一份，排除了「透過寫入時機定位載入者」這條路。

## 8. 結論：物品面板是獨立的未知渲染子系統

以上三項獨立實驗一致指向：物品說明彈窗／裝備欄／物品列文字，走的是一條
與 `re_14`～`re_21` 已定位的 FONT-100／EBOX 共用 renderer（`36AA:0864`／
`0941`／`06C0`）完全不同、目前尚未定位的程式碼路徑，很可能連字型資源
本身都不是 `FONT-100`。要正確修好這裡的中文顯示，需要一次規模與當初
renderer 系列相當的新逆向工程，而不是追加一兩個 patch 點。

## 9. 目前狀態與下一步

- `scratch_test/cjk_display_staging_v15_preferred_complete_text` 仍是唯一
  建議的可玩 checkpoint；物品名稱在其中維持原生英文（正確、無亂碼）。
- `scratch_test/cjk_display_staging_v16_name_records` 已建置完成、
  NAME-1 匯入器本身通過完整驗證與測試，但**不建議**作為使用者遊玩版本
  （物品文字顯示亂碼，比未翻譯的純英文更差）。此 staging 保留供下次
  session 直接復用做除錯。
- `tools/compile_gff_name_records.py`、321 筆修正翻譯、`cjk_mapping.json`
  的 22 個新字元、含新字元的 bank set，全部已驗證正確，只待找到物品面板
  的正確 renderer hook 後即可重新啟用。
- DOSBox-X-AI 原生橋接層是下一階段的關鍵工具；連線方式與可用 API 已在
  本文件第 7 節記錄，下次可直接繼續，不需重新發現。
- 建議下一步：在物品面板開啟時大量取樣 `CS`（而非只在 06C0 設點），
  或改在低階像素輸出 `11A4:2AF4` 設點並收集 caller return address，
  藉此縮小候選 code segment 範圍；也可嘗試在遊戲重新開機時對
  `GPLDATA.GFF` 載入路徑設中斷點，觀察 `NAME-1` 資料實際被複製到
  `0x78E74` 附近的當下呼叫堆疊。
