# v57：物品面板六項能力標籤中文化與 10px 對齊

> 日期：2026-09-10
>
> 狀態：完成獨立候選版、97 個測試，以及一次 DOSBox 載入畫面的基本確認。
> 尚待使用者正常視窗驗收完整排版、角色切換、七列攻擊及重繪。
> v55 / v56 未修改；本版承接使用者已確認的 v56「背包」顯示。

2026-09-11 使用者補充正常視窗截圖，確認物品頁六項中文顯示及效果良好。
另一張 VIEW CHARACTER 截圖仍為六列英文，符合 v57 只修改物品頁的範圍。
接續經討論同意，屬性頁改試兩欄三列，參見 `re_71`；不直接擴高原本六列。

## 1. 啟動與驗收

```powershell
& '.\scratch_test\cjk_display_staging_v57_ability_labels\launch-dosbox-x.cmd'
```

請先關閉舊版，再使用 **v57** 的啟動檔。進入物品介面應看到：

```text
力量: 24
敏捷: 15
體質: 22
智力: 13
智慧: 15
魅力: 14
```

數值依角色而變，以上為 GERAKIS 示例。本次不翻譯 PSI、AC、DROP 或 SPLIT。

請檢查六組中文／數字是否對齊、第一行是否太靠近上框，以及「背包」和物品名稱切換
是否正常。再切換 K’Ratchek，確認最後一列種族傷害仍在框內；其他共用能力標籤的畫面
也需要回歸檢查，不能以物品介面成功推定全部正常。

## 2. 真正的標籤迴圈

原物品面板在 `0x6F5A0` 傳入座標，再呼叫六項標籤函式。
本輪追到共用能力標籤 routine `0x6511F`：

- SI 從 0 到 5，`0x6512A` 取得 `DS:0EF2 + 4*SI` 的原文 far pointer。
- `0x65147` 原本以 `SI*7` 計算列距。
- 使用 `DS:0E11` 的 `%C%C%C%s` 格式，`0x65157` 呼叫原 formatter。
- 格式參數占 28 bytes；原有 cleanup、SI 遞增和回圈尾端保留。

本版替換 `0x65125..0x65156` 的 50-byte 參數準備區，透過現有 resident / FONT-local
路徑進入局部 adapter，然後回到**原本的 formatter call**。

這個 redirect 用 near call/pop 取得當前 IP，計算原 continuation，不依賴尚未定位的
overlay 載入段址，也不將 overlay segment operand 加入主 MZ relocation table。
AX=`FFEDh` 為此 adapter 的呼叫 tag；既有 NAME caller 使用正常 NAME IDs。

只有收到 `X=236, Y=8` 的座標組合才翻譯及使用 10px 列距，這是本版物品面板的新座標。
其他座標保留原文字指標、7px 列距及 formatter 參數。此限定是座標條件，不是完整的
caller 身分驗證；若其他畫面也使用同一組座標，仍可能命中，因此保留實機回歸要求。

六項中文使用 `FFF0h..FFF5h` 的固定字串快取 key，每次只解碼、繪製一行，避免六項
標籤同時搶用七個 NAME glyph slots。「背包」保留 `FFFEh` key，NAME 正常 ID 不變。
固定中文字串放入 FONT-local core，**不覆蓋原本各只有 5 bytes 的 STR: 等字串**。

## 3. 行高與水平空間

| 區域 | v57 配置 | 相對 v56 |
| --- | --- | --- |
| 六項能力中文 X | 236 | 不變 |
| 六項能力數字 X | 264 | 由 260 往右 4px |
| 六項能力 Y | 8、18、28、38、48、58 | 標籤與數字都改成 10px 列距 |
| PSI Y | 69 | 不變，仍是英文單列 |
| AC Y | 83 | 不變，仍是英文單列 |
| 武器／種族攻擊 Y | 99 起，每列 10px | 不變，七列末像素仍為 168 |

最後一項能力 10px 字形占 `58..67`，PSI 從 69 開始，中間保留一個原始像素列。
這裡沒有套用 `re_68` 的 PSI=72、AC=84 草案，因為本輪只翻譯能力標籤，原本單列
PSI / AC 保持不變就能通過垂直範圍檢查。

每個能力標籤為兩個 10px 字形加原生冒號。實際 FONT 的冒號寬度為 4，總寬 24px，
占 X=236..259；數字從 X=264 起，留下 4px 間隙。尚須正常視窗確認實際陰影與外觀。

## 4. 三個缺字與候選版 mapping

完整盤點確認缺少三字，不只先前預檢遇到的第一個錯誤：

| 新字 | ID | bank / index |
| --- | --- | --- |
| 慧 | 1314 | C5 / 34 |
| 捷 | 1315 | C5 / 35 |
| 敏 | 1316 | C5 / 36 |

以既有 append-only mapping 工具依 Unicode 順序分配，原有 ID 不變。新增 mapping
只寫入候選目錄的 `cjk-mapping-v57.json`，根目錄正式 mapping / catalog 沒有修改。
後續若以 v57 繼續擴充字庫，必須讀取此候選 mapping，不能再從 v55 mapping 重用這三個 ID。

字形使用與 v55 相同 SHA-256 的 `Fonts/Fusion_Pixel_10px.ttf`，同樣為 10px、
pixel-aligned、threshold=64、帶陰影。C5 從 34 筆擴充成 37 筆，重建 dense directory；
**原有 34 筆 glyph records 全部逐 byte 保留**，其他 C0–C4 不變。FONT-local loader
仍使用原本六個 banks，沒有新增第七銀行或更改全域高度 hook。

## 5. 驗證邊界

建置：

```powershell
python tools/build_ability_ui_candidate.py
```

輸出必須是尚不存在的目錄；可用 `--output` 指定新的驗證目錄。

- EXE 只修改標籤 adapter、標籤 Y 起點、數字 Y 算式及數字 X，共四個範圍。
- FONT header／字形／動態槽區不變，更新 FONT-local core；不改 RESOURCE 的其他內容 chunks。
- GFF 抽取驗證：1205 chunks，FONT-100 為唯一目標；1203 個非目標內容一致，另允許 GFFI-1 容器 metadata。
- 除 EXE、RESOURCE、C5 外，74 個 v56 來源檔案複製內容一致。
- 97 個測試通過，包含實際 16-bit 組譯碼執行，沒有 skip。
- 測試涵蓋六列字形、標籤／數字 Y 對齊、原有 stack／暫存器、不同 helper IP、
  非物品座標保留英文 7px、背包／NAME 與能力標籤之間的快取切換。
- 未啟用 abilities 選項仍可重現 v56 core；未啟用固定 UI 選項仍可重現 v55 core。

另啟動本版獨立 DOSBox，載入存檔後，bridge frame 的 GERAKIS 物品畫面已出現六項
中文能力標籤及原數值。**這次 bridge capture 的影像有右側重複／條紋及尺寸異常**，
所以只能作為「實際字形已繪出、載入未立即當機」的基本證據，不能用來宣稱完整排版
或重繪已通過。送出的後續角色切換輸入也未取得確實切換的畫面證據，仍列待驗收。
本輪測試僅載入候選版存檔，未執行存檔。自行啟動的 DOSBox 在正常關閉請求後仍留在
背景，核對 PID 65544 與執行檔路徑後已終止該測試程序，未操作其他遊戲程序。

重跑測試（包含現有隔離安裝的 Unicorn）：

```powershell
$env:PYTHONPATH = (Resolve-Path scratch_test/ui_emulation_deps).Path
python -m unittest discover -s tests
```

## 6. Build checkpoint

```text
DSUN.EXE
740d0d797556c05a152baecf7e7124de13c39a0ad3e7ea8b392aaf5419643a6b

RESOURCE.GFF
447a52d36a0160c3b515539f1dce91dba7af8bd18ff9c5d65aeda93bf0fde23b

FONT-100 (10044 bytes)
cafdbf59e222a5876dca94e0b95bb936c864e75cab060df738871d1eefebe184

C5 (3938 bytes)
18ec9d6aa8fb65aba20df472b0267309efa9fca7f5d7357a7bf939d7c1696e2c
```

以 `build-ability-ui-manifest.json` 為本版建置紀錄；其中 runtime_status=`not_run` 是
建置時狀態，後續有限度的 smoke check 記錄於本文件。目錄內其他舊 manifest 描述祖先。
