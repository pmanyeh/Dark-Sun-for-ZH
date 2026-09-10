# 《浩劫殘陽》繁中化：下一個 session 交接（2026-08-16）

## 2026-09-10 最新 checkpoint：v55 右側資訊區完成

目前唯一可玩基準為：

```text
scratch_test/cjk_display_staging_v55_shifted_item_panel_30px
```

使用者已實機確認 K’Ratchek 的右側能力值、PSI、AC、三組武器與 innate/racial
摘要全部收進面板，10px 格線沒有重疊，最末列不再侵入底部控制區。詳細證據見：

```text
docs/re/re_67_v55_right_panel_shift_30px_candidate.md
```

後續不得退回 v52–v54，也不得重新引入 v47/v48 global-height hook。下一階段可回到
UI／文本中文化；右側 overflow 不再是目前 blocker。

## 2026-09-10 最新 checkpoint：v52 物品 10px 格線

本檔較早內容保留歷史脈絡；物品 NAME-slot／行距工作的最新權威紀錄改見：

```text
docs/re/re_64_v52_item_grid_and_right_panel_overflow_checkpoint.md
```

目前可執行基準為 `scratch_test/cjk_display_staging_v52_ac_item_grid`。使用者已確認
v52 的說明卡、AC 到武器區，以及兩件武器內／區塊間的 10px 格線不再重疊。

新 blocker 是種族自帶武器加上裝備武器時，右側內容突破下緣；切換角色後越界
pixels 不會被清除而留下殘影。下一輪先處理右側 clip/clear rectangle 與 overflow
layout，不得再修改 global glyph-height query。v47/v48 均會在 Load Saved Game
閃退，禁止作為基底。

最後 debugger breakpoint list 已確認為空，guest 維持 running，`autolock=false`。

## 2026-08-17 最新覆寫（優先閱讀）

使用者已改變工作順序：**目前以翻譯為優先**，物品 renderer 與 DOSBox-X-AI 自動控制均
延後。正常遊玩／翻譯期間不要啟用 execution trace；逐指令 trace 會開啟 heavy log，曾造成
遊戲與音樂節奏明顯變慢，停用後已恢復正常。

已完成 `GPL-6` 巴爾卡札場景的 50 個待譯單元；安全匯入範圍、menu/TEXT 限制、6-bank
字庫與 44 項測試結果見：

```text
docs/re/re_46_gpl6_balkazar_translation_batch.md
```

正式可玩 checkpoint 仍是下文的 v26；GPL-6 工作包尚未合併或實機測試。

> 本文件取代 2026-08-15 handoff 的「目前狀態／下一步」用途；舊 handoff 保留為歷史脈絡，
> 而且目前已有使用者未提交修改，**不要覆寫、清理或重設**它。  
> 使用者要求：回覆繁體中文；每次工具操作前先用一句話說明目的；不要清理 dirty worktree。

## 0. 本次完成事項

已完成並實機驗證：

- 找到 GPL-3 外部入口 ABI，修好鬥獸場出口 Yes/No 觸發與轉場。
- 找到 `GPLDATA.GFF/GPLI-1` 的 6-byte 間接事件表，修好兩名受綁囚犯的 Talk 對話。
- 保留／驗證競技場戰鬥觸發正常。
- 恢復 EBOX `line-gap=2`，中文對話行距正常。

詳細技術脈絡見：

```text
docs/re/re_43_exit_trigger_entrypoint_and_region_format_narrowing.md
docs/re/re_44_gpl_external_entry_abi_and_prisoner_talk.md
docs/re/re_45_v26_gpli_event_relocation_official_checkpoint.md
```

## 1. 唯一正式可玩 checkpoint

```text
scratch_test/cjk_display_staging_v26_gpli_event_relocation_gap2
```

它已通過下列使用者實機回歸：

1. 兩名受綁囚犯均可開啟 Talk 對話；
2. 出口 Yes/No 對話出現；
3. Yes 後正常轉場；
4. 競技場戰鬥可觸發；
5. 中文對話行距正常。

關鍵 build 身分：

```text
DARKSUN.EXE  a4b6c99a281a7b4c34412287fd111938bdef2298362e402bb72ba2b6e60148f6
RESOURCE.GFF 4a8fe1be2a4161622545d39c50d54d3312a4e60afed44aa49c621f349601c726
GPLDATA.GFF  0065d7de6499fd0f538284fd3787f71d8bf126660e3b054164b89a87ae11365d
```

`base.conf` 已恢復 `autolock=false`，符合使用者「下次啟動不要自動鎖鼠」的偏好。
除非使用者明確要求 agent 操作滑鼠，下一次啟動維持此設定，且不要把主機鼠標移進 DOSBox。

## 2. 新的工作優先順序

使用者已指定後續工作順序：

1. 修復「物件說明／裝備欄／物品列」顯示 Base94 亂碼的 renderer 問題；
2. 開始處理 UI 中文化；
3. 最後處理多選項對話的選項文字中文化。

不要為了這三項工作重新研究 DOSBox 啟動、Base94、CJB1、字型格式、既有 EBOX renderer、
GPL-3 外部入口 ABI 或 GPLI-1 重定位。那些結論已可直接沿用。

## 3. 第一優先：物件說明 renderer 定位與修復

### 3.1 問題現況（已知且不可重複踩坑）

`NAME-1` 已完整逆向，為 `GPLDATA.GFF` 的固定寬度表：`25 bytes × 322 records`。
`tools/compile_gff_name_records.py` 已正確把 321 筆物件名稱編碼／原地寫回，所有 container
驗證與 unit tests 均通過。資料本身不是問題。

但物品說明彈窗、右側裝備欄、底部物品列會把 Base94 triple 當 ASCII 顯示，例如：

```text
^$3^&k^'>  ->  V⁄%V&5V"0（示意的亂碼結果）
```

已排除：

- EBOX／SPIN 共用 renderer：`36AA:0864`、`36AA:0941`、glyph draw `36AA:06C0`；
- `36AA` 內另 10 個 `mov al, es:[bx]` 候選；
- NAME-1 是每次重繪才複製的暫存字串：已定位的載入副本在當時測試為 `7800:0E74`
  （實體 `0x78E74`），切換面板時沒有寫入命中，表示它被唯讀重複讀取。

不要再靠上述已排除點設大範圍 breakpoint；那只會反覆停在角色名、按鈕、數值或背景 UI。
完整證據必讀：

```text
docs/re/re_41_name1_fixed_record_importer_and_item_panel_renderer_gap.md
docs/re/re_14_renderer_trace_checkpoint.md（標準 bridge breakpoint 操作程序）
```

### 3.2 建議的安全起點

**不要修改 v26。** 物件名稱翻譯測試必須另建 v27（或更高）staging；v26 是可回退的正式版本。

先把現有 GPLI 修補與 NAME patch 合成，使用 v17 的 5-bank package（其 mapping 包含 NAME 與
開場對話所需字元）：

```powershell
python tools/compile_gff_name_records.py `
  --prior-package scratch_test/gpl5_gpli_relocation_v1/gpl-dialogue-patch.json `
  --translations localization/NAME_objects_translated.json `
  --mapping localization/cjk_mapping.json `
  --output scratch_test/gpl5_gpli_name_v2

python tools/build_cjk_display_staging.py `
  --bank-package scratch_test/formal_cjk_fusion_10x10_v17_pilot_dialogue/cjk-bank-set.json `
  --spin-package scratch_test/spin_gff_import_title_newline/gff-text-replacements.json `
  --gpl-package scratch_test/gpl5_gpli_name_v2/gpl-dialogue-patch.json `
  --ebox-line-gap 2 `
  --output scratch_test/cjk_display_staging_v27_item_renderer_probe
```

建置後必做：檢查 manifest 的 `ebox_layout_line_gap=2`、GPLDATA 仍含 GPLI-1 修補，並跑 importer
unit tests。若 package manifest／bank fingerprint 顯示不相容，停止並先做唯讀比對；不要硬拼。

### 3.3 動態追蹤策略

使用 `D:\git\DOSBox-X-AI` 的原生 bridge，先確認使用者已把遊戲停在可安全測試的物品 UI。

1. 在開啟物品面板之前清除舊 breakpoint，確認 `list_breakpoints()` 為空。
2. 不要再只盯 `36AA`。在「面板由未開啟 → 已開啟」的一小段期間，使用有限、可移除的
   取樣／低階 caller tracing，收集實際活躍 code segment；優先縮小 code segment，再設精準
   code breakpoint。
3. 若使用低階像素輸出點 `11A4:2AF4`，只把它當作候選 caller 篩選器；`re_14` 已證明其
   周邊常是 image／RLE／VGA blit，不可直接把任何命中當文字 renderer。
4. 每次命中都保存：`CS:IP`、`AX/BX/CX/DX/SI/DI`、附近反組譯、以及 `SI/DI` 是否指向
   NAME buffer／Base94 prefix。先證明「讀取 NAME string 的迴圈」，再追到 glyph lookup。
5. 找到 consumer 後，先製作只識別 prefix `^` 的最小觀察 patch／trace；證實它能進入
   Base94 resolver 後，才整合現有 CJK resolver。不要一開始就改多個 renderer 位址。
6. 修補版需驗證：物品說明、右側裝備欄、底部物品列；並回歸 v26 的囚犯、出口、轉場、戰鬥。

bridge 現已提供客體 framebuffer capture：`DOSBoxClient.capture_frame(format="png")` 可直接取得
不含桌面／視窗框／主機游標的 PNG；客體 running 時可用，debugger stopped 時會因沒有新 frame
回傳 `EXECUTION_TIMEOUT`。但它仍沒有 capture 狀態 API 或可靠絕對滑鼠點擊；需要操作 UI 時
優先由使用者操控，agent 可用 frame capture 做畫面觀測。不要以 OS 桌面自動化作為正式方法。

啟動規則（2026-08-17）：一般人工操作 staging 必須使用 `autolock=false`。只有 agent 明確要
執行自動滑鼠控制時，才可在建置時加 `--mouse-autolock` 產生 `autolock=true`；完成自動控制後
應回到預設 false。`build_cjk_display_staging.py` 已將此規則設為預設並寫入 manifest。

## 4. 第二優先：UI 中文化的範圍與研究順序

### 4.1 先做分類，不要直接批次替換 EXE 字串

目前 catalog 已有候選類別：

```text
exe_ui_candidate     369
exe_format_or_ui      54
text                  60（角色標籤等，非直接 EXE UI）
```

這些是候選，不等於都能翻譯。可能混有格式字串、除錯訊息、資料標籤、overlay 內碼與不會在
玩家畫面出現的文字。直接把它們轉 Base94／改寫 EXE 是高風險且可能破壞 MZ relocation。

起點：

```text
docs/re/re_10_opends_roundtrip_and_localization_catalog.md
docs/re/re_40_v15_spell_and_dialogue_ui_regression_confirmation.md
localization/catalog/localization_manifest.csv
localization/catalog/localization_manifest.json
```

### 4.2 建議階段

1. 從主選單、Load/Save、角色／物品 UI 逐畫面建立「可見英文 string → 儲存檔案／offset →
   consumer renderer」清單；每筆都需附一張實機證據或可重複觸發步驟。
2. 先挑 1～3 筆短、靜態、已證明經 CJK-capable renderer 的 UI 字串做最小 probe。
3. 若儲存在 EXE，先確認所在 segment 是固定資料、是否涉及 overlay／MZ relocation、以及替換
   後是否會改變後續指標；不要假設它跟 GFF string table 同一格式。
4. 只有 probe 正確顯示且 layout 不壞後，才設計對應 importer／package；每個 UI 子系統可能
   都有不同 renderer，尤其物品 UI 仍是未知路徑。
5. 翻譯要同時考慮按鈕寬度、快捷鍵、反白／hover、字串格式 `%`、CRLF、可否換行；不要把
   英文縮寫一律翻成長中文。

本輪不把 `MORE` 變色當優先事項。它是已知 polish，不能用降低行數、改 `SI=5` 或犧牲第
10 列來「修好」。

## 5. 第三優先：多選項對話中文化

### 5.1 已知格式與限制

`gpl menu` opcode `0x48` 把一整個選單的全部選項放在**同一條指令**；每個選項是一組：

```text
(option_text_expression, branch_target_expression, flag_expression)
```

現有 `dialogue_occurrences.json` 對同一個 menu 的 74 筆選項使用同一 instruction offset。
目前 importer 的一 offset 一 edit 模型會報：

```text
multiple dialogue edits target the same instruction offset
```

這 74 筆因此仍保持英文。詳見：

```text
docs/re/re_42_opening_arc_dialogue_batch_and_gpl_branch_relocation_gaps.md（第 4.3、5.1）
```

### 5.2 正確實作順序

1. 先擴充 `relocate_json_strings`／其輸入模型，讓同一 `0x48` instruction 能以一組 edits
   同時修改多個 option text；不可再以 offset 當作唯一 edit key。
2. parser 必須解析 menu header 與所有三元組，逐筆以原文／序號比對目標 option，拒絕模糊或
   重複匹配。輸出時把整條 `0x48` instruction 重編碼一次。
3. 保留既有 `0x48` 第二 expression 的 branch-target relocation；這正是先前「點選選項就
   卡死」的修復，任何重構不得移除。也保留 `0x29 orelse` 與既有外部入口／GPLI 規則。
4. 先補 unit tests：多筆同 offset、僅一筆變長、所有選項變長、branch target 位移、重複／
   找不到原文應 fail closed、舊單選項 import 行為不變。
5. 建一個只翻譯 1 個已知 menu 的小 package，實機確認選項顯示、每個選項都可點、分支結果
   正確、取消／返回正常；再擴充到 74 筆。
6. 選項若太長，必須先量測 menu UI 是否支援換行／捲動；不支援時採短譯，不要讓 importer
   自動插入換行而改變 GPL 語意。

注意：`TEXT-gstring` 的 Dag／Halton／Garn／Magramar 等 60 筆是另一種 TEXT chunk importer
工作，與 `gpl menu` 74 筆選項不同；不要把兩者混成同一個 patch 規則。

## 6. 測試、啟動與安全邊界

- 任何新 build 用新 staging 資料夾，builder 不覆寫既有 output。
- 先跑相關 unit tests，再做實機；修改 GPL importer 時至少跑：

```powershell
python -m unittest tests.test_gpl_dialogue_importer
python -m unittest tests.test_gff_name_records_importer
python -m py_compile tools/compile_gpl_dialogue_patch.py tools/compile_gff_name_records.py
git diff --check
```

- DOSBox-X-AI 在 `D:\git\DOSBox-X-AI`，bridge 位於 `127.0.0.1:9876`；不要重頭研究
  它的啟動／連線方式。輸入只在 guest running 時使用，除錯讀取只在 stopped 時使用。
- 標準停點程序：pause → 設定／列出 breakpoint → continue → 命中後確認 stopped/CS:IP →
  讀 CPU／memory／disassembly → 刪除 breakpoint → 確認清空。
- 不得清理／重設 `D:\git\Dark Sun Series` 或 `D:\git\DOSBox-X-AI` 的 dirty worktree。

## 7. 未提交工作摘要

### Dark Sun Series

本輪新增／修改的核心成果包括：

```text
tools/compile_gpl_dialogue_patch.py          # GPLI-1 event target relocation
tests/test_gpl_dialogue_importer.py          # GPLI relocation test
docs/re/re_44_gpl_external_entry_abi_and_prisoner_talk.md
docs/re/re_45_v26_gpli_event_relocation_official_checkpoint.md
docs/re/HANDOFF_NEXT_SESSION_2026-08-16.md   # 本文件
```

另有使用者既存或先前 session 未提交修改（含 `HANDOFF_NEXT_SESSION_2026-08-15.md` 與
`tools/build_cjk_display_staging.py`）；先用 `git status --short` 判讀歸屬，絕對不要 reset。

### DOSBox-X-AI

本輪僅新增文件，尚未實作 Phase 7 功能：

```text
D:\git\DOSBox-X-AI\docs\phase7-observability-and-autonomous-control-requirements.md
D:\git\DOSBox-X-AI\docs\case-study-dark-sun-gpli-debugging.md
```

它們是後續 agent 可獨立處理的功能規格與案例集，不是 Dark Sun 工作的前置阻塞條件。

## 8. 必讀順序

下一個 session 先依序閱讀：

```text
docs/re/HANDOFF_NEXT_SESSION_2026-08-16.md
docs/re/re_45_v26_gpli_event_relocation_official_checkpoint.md
docs/re/re_41_name1_fixed_record_importer_and_item_panel_renderer_gap.md
docs/re/re_42_opening_arc_dialogue_batch_and_gpl_branch_relocation_gaps.md（只讀第 4.2、4.3、5.1）
docs/re/re_14_renderer_trace_checkpoint.md（只讀第 6 節的 bridge 操作程序）
```

若要追物品 renderer，再閱讀 `re_41` 的第 7～9 節；若要做 UI 文字盤點，再讀 `re_10`；
若要實作對話選項 importer，再讀 `re_42` 的第 4.3 與 5.1。不要回頭重做已排除的地圖通行、
GPL branch、Base94、字庫或 DOSBox 啟動研究。
