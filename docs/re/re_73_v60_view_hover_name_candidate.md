# v60：檢視人物裝備格 hover 名稱解碼候選版

日期：2026-09-11

> 狀態：v60 已由使用者實機確認。VIEW CHARACTER 的測試項目均正常，裝備格
> hover 名稱可正常顯示；對物件按右鍵時，說明卡也可正常顯示。v60 可作為後續
> 角色頁下半部中文排版的基準。

承接 v59 的右鍵互動修復，本版只處理 VIEW CHARACTER 裝備格底部 hover 名稱。
`0x8A925` 原路徑仍將 NAME-1 的 25-byte Base94 記錄直接交給舊 formatter，因而
顯示傳輸字串而非中文字。

候選版以既有、已用於其他物品名稱 consumer 的 NAME-slot cache 解碼該指標。
原 14-byte 位址計算序列替換為 DS-relative redirect，回到 overlay 48 的 local
continuation `0x0AC3`；不新增 main-MZ relocation，也不碰 overlay relocation word。

```powershell
& '.\scratch_test\cjk_display_staging_v60_view_hover_name\launch-dosbox-x.cmd'
```

驗收時請在 VIEW CHARACTER 將滑鼠依序移到有物品的三個右側裝備格，確認底部名稱
為正常中文；再右鍵確認 v59 的說明卡仍可開啟。RESOURCE、WIND、按鈕位置、角色頁
下半部與多職業資料均未修改。

本版建置 manifest 的 `runtime_status=not_run` 記錄可重建產物剛產出時的狀態；
產出後的 DOSBox-X 實機驗證已由使用者完成，結果如頁首所記。

```powershell
python tools/build_view_hover_candidate.py --output scratch_test/v60_rebuild_check
$env:PYTHONPATH = (Resolve-Path scratch_test/ui_emulation_deps).Path
python -m unittest discover -s tests
```
