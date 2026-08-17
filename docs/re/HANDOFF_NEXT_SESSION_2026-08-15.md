# 《浩劫殘陽》中文化：下一個 AI Session 交接備忘錄

> 交接日期：2026-08-15（Asia/Taipei）  
> 工作目錄：`D:\git\Dark Sun Series`  
> 使用者語言：繁體中文  
> 原則：接續既有成果，不要從 DOSBox 啟動、字型格式或 Base94 transport 重頭摸索。

## 0. 給下一個 AI 的第一句指令

請先完整閱讀本檔，以及 `re_42`、`re_41`、`re_40`、`re_39`。保留目前 dirty
worktree，禁止 `git reset --hard`、`git checkout --`、`git clean` 或覆寫 Steam
原始遊戲。當前正式 checkpoint **仍然只有 v15**；法術說明與 Celgor 對話已於
`re_40` 實機回歸確認過關。

`re_42` 記錄的**競技場戰鬥觸發卡死已經修好並實機驗證**：根因是 `gpl global
sub`（`0x14`）指令有兩處在 GPL-2 內部自我參照（呼叫自己 chunk 內的位址，卻
用「跨 chunk」呼叫的參數形式），先前誤判成「跨 chunk 不需重定位」而完全沒調整，
導致跳轉落在翻譯後已經位移的舊位置。連同稍早修好的 `0x48 menu`、`0x29 orelse`
兩個分支重定位 bug，`scratch_test/cjk_display_staging_v20_global_sub_fix`
已確認競技場開場、戰鬥觸發、戰後劇情銜接全部正常。

但緊接著做全程回歸時，發現**新的、獨立的問題**（`re_42` 第 9 節）：選過
GPL-4「衝向西側出口」逃獄選項後，走到出口沒有任何反應，無法真正離開競技場；
v15 在對應情境下能正確顯示過場確認提示。已排除「地圖觸發表（`ETAB`）內嵌
GPL 舊位址」與「`0x14`／`0x48`／`0x29` 已知重定位缺口」兩個假設，皆未命中。
目前推測是「劇情旗標（`gflag`）與地圖通行資料（`GMAP`/`RMAP`/`ETAB`，33 個
`RGN*.GFF` 區域檔）之間的關聯機制」，這是一套完全未逆向過的全新二進位格式，
**這是下一個 session 最優先要調查的問題**，具體方向見 `re_42` 第 9.2 節。
不要在還沒摸清楚格式前貿然修改 `GMAP`／`RMAP`／`ETAB`。

在此之前，`re_42` 第 7 節記錄的跨 chunk `0x14` 一致性缺口（GPL-4 有一個呼叫
回 GPL-2 舊位址的跨 chunk 引用，本次修復範圍只處理同 chunk 自我參照）也還沒
處理。**v20 因此仍不能升格成正式 checkpoint**。

`re_41` 記錄的物品面板（裝備欄／物品說明彈窗）中文渲染路徑調查——這是另一條
全新、尚未定位的 renderer，不要假設它與 EBOX/SPIN 共用 `36AA:0864` 路徑
（已排除）——仍然獨立待解決，優先度在地圖通行問題之後。`D:\git\DOSBox-X-AI`
是一個可用的原生 DOSBox-X 除錯橋接層，見本檔第 15 節，直接沿用即可，不需要
重新發現。

## 1. 目前最佳可玩 checkpoint

```text
scratch_test/cjk_display_staging_v15_preferred_complete_text
```

此版組合：

- 原生 FONT/layout height：9 rows；
- CJK draw height：10 rows；
- CJK record：10×10，102 bytes；
- EBOX 額外行距：2 pixels（應稱「行距」，不是「行高」）；
- EBOX 實際 next-page delta：`-3`；
- 原版 UI state `SI=5` 保留；
- Base94、四個 CJB1 banks、resident scratch cache；
- 172 筆中文 SPIN 法術文字與「法術名稱後換行」；
- Celgor 開場四筆中文 GPL dialogue；
- DOSBox-X 視窗 1280×960，即遊戲 640×480 的整數 2×。

重要 SHA-256：

```text
DSUN.EXE
15e8f818bb7a69fa972543c5bd5799717d245db8ca2a1c89eede6d1b59dc4ba0

RESOURCE.GFF
4a8fe1be2a4161622545d39c50d54d3312a4e60afed44aa49c621f349601c726

GPLDATA.GFF
9c31685a2538cdf10cb635965922c9b00ddf8500f434a5e4886aa02612ff7c47
```

完整 manifest：

```text
scratch_test/cjk_display_staging_v15_preferred_complete_text/build-manifest.json
```

交接時 v15 正在執行：

```text
PID 35000
```

新 Session 不應假設 PID 必然仍存在；先用：

```powershell
Get-Process dosbox-x -ErrorAction SilentlyContinue |
  Select-Object Id,StartTime,Path,MainWindowTitle
```

### 1.1 v16（已建置，但不要當成 checkpoint 使用）

```text
scratch_test/cjk_display_staging_v16_name_records
```

v16 = v15 + 321 筆裝備／物件名稱翻譯（`GPLDATA.GFF/NAME-1`）。匯入器本身
（`tools/compile_gff_name_records.py`）已通過完整驗證與自動測試，翻譯位元組
確實正確寫入記憶體，但物品面板（物品說明彈窗／裝備欄／物品列）目前把這些
Base94 triple 當成逐位元組 ASCII 印出來，顯示為亂碼，比純英文還差。詳見
`re_41`。**不要把 v16 推薦給使用者遊玩**，除非已經解決第 15 節的 renderer
缺口。v15 仍是唯一建議的可玩版本。

### 1.2 v20（已建置並實機驗證修復，但尚未完整回歸，先不要升格為 checkpoint）

```text
scratch_test/cjk_display_staging_v20_global_sub_fix   目前功能正確的最新版本
scratch_test/cjk_display_staging_v19_orelse_fix       已知會卡死，被 v20 取代
scratch_test/cjk_display_staging_v17/v18              修復過程中間版，忽略
```

v20 = v15 + 248 筆 GPL-2~5 開場劇情對話翻譯 + 5-bank runtime，且已修好三個真實
GPL 重定位 bug（`0x48 menu`／`0x29 orelse`／`0x14 gpl global sub` 自我參照，
詳見 `re_42`）。實機確認競技場開場、戰鬥觸發、戰後逃獄劇情銜接全部正常。

**尚未做完整全程回歸**，也還沒修好 `re_42` 第 7 節記錄的已知缺口（GPL-4 有
一個跨 chunk 呼叫回 GPL-2 舊位址，本次只處理同 chunk 自我參照）——先用 v20
把 GPL-2~5 完整劇情走一輪確認無誤，再考慮升格為新 checkpoint。v17／v18／
v19 都已被 v20 取代，不要再使用。

## 2. v15 已確認與目前取捨

使用者實機已確認 v13（與 v15 同一核心 EXE/RESOURCE 行為）：

- 中文大字清楚；
- 中文底部與右下陰影完整，不再被裁切；
- 行距可接受；
- `MORE` 可點並能翻到剩餘文本；
- 上一頁／返回可運作。

v15 的已知取捨：

- `MORE` 暫時不會提供原版的 hover／按壓變色；
- 使用者明確同意先捨棄此視覺效果，以文字完整性優先；
- 這是 polish，不是內容不可達或按鈕失效。

不要把 v14 當成最佳版。v14 恢復 `MORE` 變色，但中文字第 10 列再次被 clip。

## 3. 正確 DOSBox-X 啟動方式（非常重要）

正確 executable：

```text
D:\git\DOSBox-X-AI\dosbox-src\bin\x64\Release\dosbox-x.exe
```

必須：

1. working directory 設為 staging 根目錄；
2. 依序載入 `base.conf`、`graphics.conf`、`game.conf`；
3. 由 `game.conf` 呼叫 `DARKSUN.BAT`；
4. 固定 7000 cycles；
5. 不可直接執行 `DSUN.EXE`，那是過去多次「DOSBox 有開但未進遊戲」的原因。

PowerShell 範例：

```powershell
$stage = (Resolve-Path `
  'scratch_test\cjk_display_staging_v15_preferred_complete_text').Path
$exe = 'D:\git\DOSBox-X-AI\dosbox-src\bin\x64\Release\dosbox-x.exe'
Start-Process -FilePath $exe -WorkingDirectory $stage `
  -ArgumentList @('-conf','base.conf','-conf','graphics.conf','-conf','game.conf')
```

若要切版，可以自行關閉由 AI 啟動的明確 DOSBox-X 測試 PID；使用者已指出不必每次
要求他手動關閉。先核對 PID/ProcessName，再：

```powershell
Stop-Process -Id <PID> -Force
```

不要廣泛終止其他不明行程。

## 4. 目前字型事實

目前 playable banks **不是倚天字型**，也不是 Noto Sans TC：

```text
Fonts/Fusion_Pixel_10px.ttf
```

它是 provisional 小字型。使用者會繼續找合適的倚天字型，流程完成後再替換。

`Fonts/` 已有倚天相關媒體／檔案：

```text
ET353S.iso
ascfont.15
stdfont.15
usrfont.15m
eten.h
font.c
main.c
```

倚天媒體研究見 `re_30`、`re_34`。不要把 15-row 全域 FONT 說成「永久不可玩」；
使用者已明確要求保留為後續研究方向。只可說「目前直接把 global FONT height 改成
15 的方案會破壞版面／分頁，因此現階段未採用」。

## 5. 為何 v15 是 9-row layout / 10-row CJK draw

Fusion Pixel 10px 的絕大多數中文字主 bitmap 正好是 9×9。Dark Sun 的陰影向右下
偏移 `(x+1,y+1)`，因此完整主字形＋陰影需要第 10 列。

已否決：

- 10×9 無陰影：下緣完整，但清晰度較差，而且該 A/B 的 `MORE` 變色也消失；
- font size 9＋陰影：下緣完整，但字太小、糊成一團；
- 將底列陰影向右箝制：字清楚且 `MORE` 變色恢復，但使用者仍看見下緣被裁感；
- global FONT height 15：改變所有 UI layout，一頁四行變兩行，曾造成不可達文本；
- 只增加 draw Y：最後一行超出 clip，只剩字頂，看似亂碼。

v15 做法：

- FONT global height 仍為 9；
- CJB1 bank height 為 10；
- scratch record 為 `u16 width + 10*10 pixels = 102 bytes`；
- renderer height helper 位於 `36AA:53D6`；
- glyph height load patch 位於 `36AA:0704`；
- marker byte `0x7F` 的 shared draw/clip path 使用 10，其餘 glyph 使用 9；
- resident cache 機器碼仍為 218 bytes，落在 `36AA:545A..5533`。

v14 曾嘗試以完整 word 區分 CJK `0x017F` 與 UI `0x007F`。結果 `MORE` 變色恢復，
但中文第 10 列又被裁，表示尚有一個 clip-height query 共用 `0x007F`。未來若要同時
恢復變色與完整文字，應追這個 clip/control 狀態，不應退回 9-row CJK，也不必立刻
改做 SDL overlay。

## 6. EBOX 行距與分頁的已知機制

重要 runtime segment／file base：

```text
EBOX runtime segment       341D
EBOX overlay file base     0x31390
FONT renderer segment      36AA
FONT renderer file base    0x33C60
```

Base94 EBOX patch：

- `341D:0214..0239`：`^xy` 寬度固定 10 pixels；
- `341D:028A`：layout source index 對 `^` 額外前進兩 bytes；
- `341D:04A6`：layout advance call；
- `341D:01CD`：line table 儲存高度時加 2 pixels；
- 所有 patch 先檢查 MZ relocation overlap。

可見行計算：

```text
341D:1829
```

捲動起始行：

```text
EBOX object + 0x8A
writer 341D:1811
redraw 341D:1821 -> 341D:055D
```

原版 next page 一次送 `-5`。增加行距後本頁只能顯示三行，總行數四行；`-5` 越界
會被核心拒絕，所以過去出現「畫出 MORE 但點了不動」。

正確 v11+ 修正不是把四個 `mov si,5` 改成 3。這會讓翻頁成功卻破壞 UI feedback。
現在保留全部 `SI=5`，只在兩個 next-page call site 將：

```asm
mov ax,si
neg ax
push ax
```

等長改為：

```asm
push byte -3
nop
nop
nop
```

file offsets：

```text
0x7CDBC
0x7DBC5
```

previous page 仍做五次逐行 `+1` 回退；到 0 後多餘兩次由原生負值邊界檢查拒絕。

## 7. CJK transport / bank / cache

Unicode mapping：

```text
localization/cjk_mapping.json
```

目前 923 active glyphs（901 舊 + 本次 NAME-1 翻譯新增 22 個）、四個 banks、
append-only ID；前三個 bank 與 v15 原始 bank SHA-256 完全一致，第四個 bank 是
嚴格附加。transport 是 printable Base94
triple：

```text
^xy
```

規則：

- digits `0x21..0x7E`；
- capacity 8835；
- literal `^` 禁止；
- `^^^` / ID 5795 永久保留，runtime 回傳單一 `?`；
- 不可改成一般 Big5 雙位元組假設。

resolver hooks：

```text
36AA:094A  draw byte consumer
36AA:07F8  width pass
36AA:09A2  formatted-text pass
```

resident cache：

```text
36AA:545A..5533
```

每個 glyph 依 bank 檔 `C0.BIN..C3.BIN` 做 open/read/close。不要把程式擴到
`36AA:5534` 以上；spell UI 會覆寫該區。此前保留 file handle 的版本曾導致法術切換
閃退，現行 open/read/close 是安全方案。

## 8. 翻譯與 importer 狀態

SPIN：

- 172/172 已有中文 package；
- 法術名稱後由 compiler 插入 CRLF，canonical translation 不含這個格式性換行；
- 使用者已確認 BLESS 顯示為「祝福術：」獨立一行，說明在下一行；
- package：
  `scratch_test/spin_gff_import_title_newline/gff-text-replacements.json`。

GPL dialogue：目前只正式導入 Celgor 開場四筆：

```text
DLG_f6c2fbaa84a9  今日法師賽爾戈將迎戰一頭兇猛的狂暴獸。
DLG_13ab12eaff4a  敬請觀賞！
DLG_6294a22b2cbb  別擔心，
DLG_67aa8858af43  。很快就輪到你了。退後觀看這場戰鬥吧。
```

動態 `Gerakis` 名稱仍是原 GPL expression，沒有被攤平成靜態字串。四份 catalog 已同步：

```text
localization/catalog/dialogue_units.csv
localization/catalog/dialogue_units.json
localization/catalog/localization_manifest.csv
localization/catalog/localization_manifest.json
```

GPL package：

```text
scratch_test/gpl_celgor_zh_v1/gpl-dialogue-patch.json
```

`tools/compile_gpl_dialogue_patch.py` 支援 variable-length inline compressed GPL/MAS string，
會：精確 fingerprint、Base94 encode、重定位後續 instruction offsets 與 local branches、
用 OpenDS `gpl-asm` 驗證、再比對完整 GFF chunks。只允許 GPL-2 與 GFFI-8 改變。

## 9. 主要工具

```text
tools/cjk_localization_pipeline.py
  inventory / build-banks / encode / compile-catalog /
  compile-gff-text / pack-gff-text / verify-banks / audit-eten

tools/compile_gpl_dialogue_patch.py
  variable-length GPL dialogue importer

tools/compile_gff_name_records.py
  GPLDATA.GFF/NAME-1 固定 25-byte 記錄原地覆寫匯入器；支援 --prior-package
  疊加在既有 darksun-gpl-dialogue-patch 封裝之上

tools/build_cjk_display_staging.py
  建立隔離可玩 staging；現在允許 native FONT 9 + CJK draw 10

tools/patch_dsun_scratch_cache.py
  resolver、resident cache、EBOX wrap、line gap、pagination、10-row draw patches

tools/cjk_scratch_cache.asm
  DOS bank loader

tools/font100_tool.py
  FONT-100 parse/render/試驗工具
```

OpenDS 工具預設位置：

```text
vendor/opends/target/release/gff-cat.exe
vendor/opends/target/release/gpl-disasm.exe
vendor/opends/target/release/gpl-asm.exe
```

如果不存在，先在 `vendor/opends` 建置，不要假設舊的 `tools/opends/...` 路徑仍存在。
靜態 x86 反組譯可用 Python `capstone`；先前已確認本機有 capstone 5.0.7。

## 10. 重建 v15 的命令

先建 10×10 full-shadow banks：

```powershell
python tools/cjk_localization_pipeline.py build-banks `
  --mapping localization/cjk_mapping.json `
  --font Fonts/Fusion_Pixel_10px.ttf `
  --font-size 10 --pixel-width 10 --height 10 --advance 10 `
  --threshold 64 --fit-mode pixel-aligned `
  --output scratch_test/formal_cjk_fusion_10x10_v11_full_shadow
```

再建 staging：

```powershell
python tools/build_cjk_display_staging.py `
  --bank-package scratch_test/formal_cjk_fusion_10x10_v11_full_shadow/cjk-bank-set.json `
  --spin-package scratch_test/spin_gff_import_title_newline/gff-text-replacements.json `
  --gpl-package scratch_test/gpl_celgor_zh_v1/gpl-dialogue-patch.json `
  --ebox-line-gap 2 `
  --window-scale 2 `
  --output scratch_test/cjk_display_staging_v15_preferred_complete_text
```

Builder 不覆寫既有 output；要重建請使用新的 staging 名稱，不要直接刪除或覆蓋使用者
正在玩的資料夾。

## 11. 測試

目前完整測試：

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

交接時結果：

```text
38 tests passed（含 NAME-1 匯入器測試與 GPL menu/orelse/global-sub 分支重定位測試）
```

修改 executable patch 後至少要做：

```powershell
python -m unittest discover -s tests -p 'test_*.py'
git diff --check -- <本次修改檔案>
```

不要只看單一 patch bytes；必須保留 MZ relocation overlap guard、RESOURCE/GPLDATA
full-container verification 與 bank hash 驗證。

## 12. 下一步建議（依優先順序）

1. **地圖通行機制調查（`re_42` 第 9 節開的坑，目前最優先，會讓遊戲卡住）。**
   選過 GPL-4 逃獄選項後走到出口沒有反應，v15 對應情境下正常。已排除
   `ETAB` 內嵌 GPL 舊位址、已知三個重定位缺口（`0x48`／`0x29`／`0x14`）
   兩類假設。目前推測與 `gflag`（劇情旗標）跟 `GMAP`/`RMAP`/`ETAB`（33 個
   `RGN*.GFF` 區域檔）的關聯機制有關，這是全新、未逆向過的二進位格式。
   具體排除過程與下一步方向見 `re_42` 第 9 節；不要在摸清楚格式前貿然修改
   `GMAP`／`RMAP`／`ETAB`。
2. **v20 完整回歸測試。** 用 `scratch_test/cjk_display_staging_v20_global_sub_fix`
   完整走一輪 GPL-2~5 涵蓋的劇情（競技場開場 → 戰鬥 → 逃獄 → 面紗聯盟引子），
   確認沒有其他卡死點，特別留意會不會踩到 `re_42` 第 7 節記錄的跨 chunk
   `0x14` 一致性缺口（GPL-4 有一個呼叫回 GPL-2 舊位址的引用，本次修復只
   處理了同 chunk 自我參照）。上述兩個問題都解決、全程無誤後才能把 v20
   升格為新的正式 checkpoint。
3. 修好 `re_42` 第 7 節的跨 chunk `0x14` 缺口，再繼續擴大翻譯到 GPL-4 之後
   的內容。
4. **物品面板 renderer 定位（`re_41` 開的坑）。** 找出物品說明彈窗／裝備欄／
   物品列實際呼叫的文字繪製函式與其字型資源。已排除：`36AA:0864`／`0941`／
   `06C0`（EBOX/SPIN 共用 renderer）、segment `36AA` 內另外 10 個候選
   `mov al,es:[bx]` 位址、目標緩衝區（`GPLDATA.GFF/NAME-1` 載入後的記憶體
   副本）本身沒有寫入行為（唯讀重複讀取，不是每次重繪都複製一份）。建議
   方向：在物品面板開啟時大量取樣 `CS`；或在低階像素輸出 `11A4:2AF4` 設點
   收集 return address 縮小候選範圍；或在遊戲重新開機、`GPLDATA.GFF` 載入
   當下設中斷點，觀察 `NAME-1` 資料被複製到記憶體的當下呼叫堆疊。
5. `MORE` 變色列為 polish：追 shared `0x007F` clip-height query 與 control redraw，不要
   以犧牲第 10 列或改 `SI=5` 換回顏色。
6. 上述都確認安全後，再擴大正式文本翻譯（`Dag`／`Halton`／`Garn`／
   `Magramar` 等 TEXT 字串表標籤與 74 句選單選項文字，需要新的匯入器/架構
   擴充才能處理，見 `re_42` 第 4.2、4.3 節）與 GPL importer 覆蓋範圍。
7. 使用者找到合適倚天字型後，只替換 bank glyph source；保持 mapping、transport、
   importer、cache 與 staging contract。

## 13. 必讀逆向工程文件

優先：

```text
docs/re/re_42_opening_arc_dialogue_batch_and_gpl_branch_relocation_gaps.md
docs/re/re_41_name1_fixed_record_importer_and_item_panel_renderer_gap.md
docs/re/re_40_v15_spell_and_dialogue_ui_regression_confirmation.md
docs/re/re_39_independent_10row_cjk_draw_and_v15_preferred_checkpoint.md
docs/re/re_38_ebox_line_gap_pagination_and_ui_feedback_proof.md
docs/re/re_37_variable_length_gpl_dialogue_importer_and_v7_checkpoint.md
docs/re/re_36_spin_title_description_hard_break_runtime_proof.md
docs/re/re_35_relocation_safe_ebox_base94_wrap_and_spell_runtime_proof.md
docs/re/re_33_global_font_height_text_loss_and_9row_recovery.md
```

底層 pipeline：

```text
docs/re/re_24_algorithmic_base94_resolver_runtime_proof.md
docs/re/re_26_cjb1_loader_contract_and_full_bank_verification.md
docs/re/re_27_resident_scratch_cache_loader_prototype.md
docs/re/re_29_cjb1_direct_read_cross_bank_runtime_proof.md
docs/re/re_31_spin_gff_transport_importer_and_roundtrip.md
```

## 14. 工作樹安全

目前 worktree 很髒，包含大量 `M` 與 `??`。這些不是垃圾；多數是尚未 commit 的完整
研究鏈、工具與測試。下一個 AI 必須：

- 先 `git status --short`；
- 保留所有不相關／既有修改；
- 僅用 `apply_patch` 做文字檔修改；
- 不執行 destructive git/filesystem cleanup；
- `scratch_test/` 是生成／驗證成果，但目前多個 checkpoint 仍用於 A/B 證據，不要
  未經使用者同意批次刪除。

## 15. DOSBox-X-AI 原生除錯橋接層（新工具，強烈建議直接沿用）

```text
D:\git\DOSBox-X-AI
```

這是一個獨立專案（`pmanyeh/dosbox-x` fork，`ai-mcp-bridge` 分支），在原生
DOSBox-X 裡內建一個只監聽 `127.0.0.1:9876`（loopback）的除錯橋接層，用
newline-delimited JSON 暴露中斷點、單步執行、暫存器／記憶體讀取（不含寫入
暫存器以外的內容）、反組譯。**我們一直在用的
`D:\git\DOSBox-X-AI\dosbox-src\bin\x64\Release\dosbox-x.exe` 本身就是這個
帶橋接層的 build**，只要它在跑，埠口就在監聽，不需要另外啟動或用 MCP 註冊。

不需要透過 MCP 工具，直接用 Python 呼叫現成的 client 即可：

```python
import sys
sys.path.insert(0, r"D:\git\DOSBox-X-AI\ai")
from dosbox_client import DOSBoxClient

c = DOSBoxClient(request_timeout=15.0)
c.connect()
c.pause_execution()                      # 讀記憶體／反組譯前必須先暫停
c.set_breakpoint("36AA:06C0")
c.continue_execution()
status = c.get_debug_status()            # {"stopped": bool, ...}
mem = c.read_memory("4B7A:FA32", 8)      # {"bytes": ["52","09",...]}
insns = c.disassemble("36AA:0930", 20)
c.set_protected_memory_breakpoint("7800:0E74")  # 寫入變化監看點（BPPM）
c.close()
```

已知限制與注意事項：

- `read_memory`／`disassemble`／`list_breakpoints` 只能在除錯器**已暫停**時
  呼叫，否則立即回傳 `DEBUGGER_NOT_STOPPED`；`get_debug_status()` 不受此限。
- 一次 `read_memory` 讀太大（例如 0xFFFF bytes）容易在忙碌時 timeout，
  逾時後如果沒有正確處理會讓後續請求的 id 對不上而全部炸開；建議單次讀
  0x4000 bytes 內，並在 catch 例外時整個重新 `connect()`。
- `set_real_memory_breakpoint`（`breakpoint.memory.real.set`）在目前這個
  build 回傳 `UNKNOWN_METHOD`；寫入監看點請改用
  `set_protected_memory_breakpoint`（`breakpoint.memory.set`，即原生 BPPM）。
- 這些位址（如 `36AA`、`4B7A`）是傳統 real-mode 風格的 `segment:offset`，
  物理位址 = `segment*16 + offset`，與先前所有 re_ 文件的定址方式一致，
  可以直接互通。
- 完成除錯後務必清空所有中斷點（`list_breakpoints()` 逐一 `delete_breakpoint`）
  並確認 `continue_execution()` 讓遊戲恢復正常執行，不要把使用者的遊戲留在
  暫停狀態。
- 該專案自身 README 標示 Phase 5C 自主 agent 驗收「未完全通過」，僅供受控
  研究情境使用；我們是直接用底層 `DOSBoxClient` TCP protocol，不經過那層
  MCP 受限介面，因此不受該驗收結果限制，但仍應謹慎操作（尤其
  `write_memory`／`write_register`／`continue_execution` 等會真的改變玩家
  遊戲狀態的操作）。

## 16. 對使用者溝通方式

- 使用繁體中文。
- 工具操作前先簡短說明目的。
- DOSBox 測試行程可由 AI 自行精確關閉／切版，不必反覆要求使用者手動關閉。
- 啟動或操作 DOSBox-X 時，不要將滑鼠移入、定位或停留在 DOSBox 視窗內。
- 每次啟動 DOSBox-X 前，先確認該 staging 的設定為 `autolock=false`；不要依賴預設值。
- 每次只請使用者驗證少數清楚的畫面現象。
- 不要把 provisional Fusion Pixel 說成倚天。
- 不要宣稱 SDL 是唯一解；現行 v15 已證明原生 renderer 可做 9-row layout / 10-row
  CJK draw。

## 17. 2026-08-16：競技場出口 ABI 修補已通過實機驗證

`re_43_exit_trigger_entrypoint_and_region_format_narrowing.md` 的地圖通行調查已結案：
問題不是 `gflag`、`GMAP`、`RMAP` 或 `ETAB`。GPL-3 的出口 callback 有未重定位的
固定外部 entry ABI，必須在 `0x07C0` 以 `0x2A clearpic` 開始。v20 的翻譯使它移至
`0x07D6`，故門口無對話。

已驗證候選：

- 封包：`scratch_test/gpl3_exit_entry_abi_v1`
- 可玩 staging：`scratch_test/cjk_display_staging_v21_exit_abi_fix`
- 實機：出口出現繁中確認對話，選 Yes 後正常轉場至庫爾扎克後續對話。

另有從同一候選封包重新建置、且由 staging builder 再抽取 GPL-3 驗證 ABI 的：

- `scratch_test/cjk_display_staging_v22_exit_abi_guard_rebuild`

`tools/compile_gpl_dialogue_patch.py` 新增：

```text
--require-fixed-entry GPL:3:0x07C0:0x2A
```

未來重組包含 GPL-3 的對話封包時必須使用這個 guard；若入口位移，建置會失敗。v21
尚是實機驗證 staging，v22 是同 payload 的可重建 guard 驗證 staging；兩者均未升格
正式 playable checkpoint。下一步是完成短回歸後才決定升格。
