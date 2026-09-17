# v58b：屬性資料頁兩欄三列中文能力候選版

> 日期：2026-09-11
>
> 狀態：114 個測試通過；DOSBox 已成功載入、開啟屬性頁並切換兩位角色。
> 尚待使用者正常視窗驗收排版、裝備格操作及重繪。v57 不變。

## 1. 使用方式與範圍

請使用 **v58b**，不要使用被拒絕的第一個 v58 目錄：

```powershell
& '.\scratch_test\cjk_display_staging_v58b_view_character_columns\launch-dosbox-x.cmd'
```

載入存檔後按 V 開啟 VIEW CHARACTER。能力區試排為：

```text
力量: 19    智力: 16       裝備格 1
敏捷: 21    智慧: 19       裝備格 2
體質: 19    魅力: 15       裝備格 3
```

這是布局示意，裝備格實際高 18px，不與文字逐列對齊。數值仍取自角色資料，沒有修改。
種族／性別、陣營、職業和下半部資料保留原文與原座標；它們的中文化尚未完成。
物品頁保留 v57 的六列中文、背包及右側武器排版。

請驗收：

1. 六項中文與各自數字是否對齊，左右兩欄是否容易閱讀。
2. 用 1–4 或角色頭像切換角色，文字和裝備圖示是否正確更新。
3. 右側直排三格的 hover／點擊／右鍵行為是否對應新位置，舊位置不應仍有反應。
4. 最右側裝備格是否碰到框線，最長種族／陣營文字是否與第三格重疊。
5. 關閉再開啟屬性頁，是否有舊橫排裝備框或文字殘影。
6. 按 I 回到物品頁，確認背包與 K’Ratchek 最後一列傷害仍正常。

## 2. 屬性頁獨立路徑

這個頁面不呼叫 v57 修補的共用能力標籤迴圈，而是自己在另一個 overlay 繪製：

- 標籤迴圈 `0x8A0E8`，原 formatter call `0x8A11F`。
- 數字迴圈 `0x8A12F`；數值讀取與入棧到 `0x8A148` 都保留。
- 數字 formatter call `0x8A176` 保留。
- 格式字串分別是 `DS:3351` / `DS:335A`。

v58b 只修補兩段準備參數的機器碼：

| 檔案範圍（末端不含） | 長度 | FONT-local tag |
| --- | --- | --- |
| `0x8A0E8..0x8A114` | 44 bytes | `FFECh`，標籤 |
| `0x8A149..0x8A16B` | 34 bytes | `FFEBh`，數字 |

redirect 沿用 call/pop 計算原 overlay continuation，再透過既有 DS-relative trampoline。
標籤使用 v57 已有的 `FFF0h..FFF5h` cache keys、相同中文字串及 C0–C5 字形。
數字 adapter 保留原先已壓入的數值，只重新準備原格式參數及新座標。
沒有修改原文 STR: 等固定大小字串、根目錄 mapping、C5 或存檔。

## 3. 座標與裝備格來源

| 區域 | 原始遊戲座標 |
| --- | --- |
| 左欄標籤／數字 X | 149／177 |
| 右欄標籤／數字 X | 201／229 |
| 三列 Y | 40、52、64 |
| 中文字高／列距 | 10／12px |
| 種族、陣營 Y | 86、93，不變 |
| 三個裝備格新位置 | (259,42)、(259,61)、(259,80) |

標籤寬度為 10+10+4=24px，數字前留 4px；左右欄起點差 52px。
能力區最後字形末像素是 73，種族文字仍從 86 起，可保留未來翻譯的垂直空間。
兩位數的右欄數字末端小於裝備格 X=259；更長數字與其他語言內容仍需另外驗證。

裝備格是 **APFM 控制項**，不是獨立 BUTN。WIND-11500 內的 placement：

| APFM ID | WIND 內記錄起點 | 原座標 | 新座標 |
| --- | --- | --- | --- |
| `2BCFh` (11215) | `0x64F` | (205,42) | (259,42) |
| `2BD0h` (11216) | `0x66D` | (224,42) | (259,61) |
| `2BD1h` (11217) | `0x68B` | (243,42) | (259,80) |

每個 placement 的 +8/+10 是 X/Y；APFM 本體的尺寸為 18×18。只更改這三組座標，
不重畫背景或改 APFM 的 callback。`0x8AA21` 的空格底圖及 `0x8AC26` 的裝備圖示
均以控制項 ID 查詢其 rectangle，因此會隨 placement 移動。
這是繪圖／控制項位置同步的靜態依據；不等同於 hover／點擊已全部實機通過。

## 4. 第一版 v58 為何被拒絕

第一版覆蓋了原 `mov ax,0430h` 等 surface 指令，並在 FONT-local adapter 重建它們。
但 `0430h` 是 overlay loader 要調整的 segment operand，不是可直接複製的執行期段址。
原位置的 relocation 還會覆寫新 redirect 的 bytes，造成載入異常。

overlay map 確認該段為 index 48，file_start=`0x89E70`、size=3843、relocation_count=356。
周邊 fixup 包含 `0x8A115`、`0x8A116`、`0x8A16C`。v58b 的兩個替換區都在它們之前結束，
回到原有 surface 指令，保留 loader 的處理，主 MZ 和 overlay relocation 資料均未修改。

建置器新增 `verify_overlay_relocations`：使用既有 ovr-map parser，保守檢查 fixup 的兩個
bytes，只要任何一個與替換區重疊就拒絕。舊 v58 hook 可由此檢查明確拒絕。
第一版 v58 目錄保留作為失敗證據，**不可作為可用版本**。

## 5. 驗證結果與邊界

- 114 個單元／機器碼測試通過，沒有 skip；含原 v55–v57 回歸、屬性頁標籤／數字的
  兩欄座標、stack／暫存器保留、三組 WIND 座標、overlay relocation overlap guard。
- v57 不啟用 view-character 選項時仍可重現原 FONT core。
- EXE 只改兩個上述範圍；1205 個 GFF chunks 中僅 FONT-100、WIND-11500 是目標。
  1202 個非目標內容一致，另允許 GFFI-1 容器 metadata。
- 78 個其他來源檔案複製內容一致，包括 C0–C5、候選 mapping、launcher 和設定。
- v58b 實際載入存檔成功，按 V 顯示 GERAKIS 兩欄中文和直排裝備，按 2 切換至
  K’Ratchek 後六項能力及裝備圖示更新。未見舊橫排框留在原位。
- 關閉屬性頁、按 I 顯示 GERAKIS 物品頁，仍為 v57 六列中文與武器區。
  再按 2 確認 K’Ratchek 物品頁更新；此候選存檔的裝備不足七列，不能據此宣稱最壞七列已實測。
- 內部 capture 持續有影像比例與右半部條紋異常，與先前版本相同，因此只能記錄
  可辨識的內容／排列；最終正常視窗外觀仍請使用者驗收。
- 曾向新裝備格送出滑鼠操作，但沒有取得足夠可辨識的反應證據，**點擊驗收仍未完成**。
- 沒有執行存檔；僅操作自行啟動的測試 DOSBox。

重建及測試：

```powershell
python tools/build_view_character_candidate.py --output scratch_test/v58b_rebuild_check
$env:PYTHONPATH = (Resolve-Path scratch_test/ui_emulation_deps).Path
python -m unittest discover -s tests
```

輸出目錄必須不存在。以 `build-view-character-manifest.json` 為準；其他繼承的 notices／
manifests 描述祖先版本。此 manifest 的 `not_run` 是建置時狀態，本文件補記之後的 smoke test。
v58b 使用原 `cjk-mapping-v57.json`，其中慧／捷／敏 IDs 1314–1316 必須保留。

## 6. v58b build hashes

```text
DSUN.EXE
9ac8f29f1a9525ca7f54a768a8c5501e23d8b22812e3c28275c8e09891b61990

RESOURCE.GFF
3c8291a8a4b793bb4e2c3f382142a63ec9c4744d4a67f0abc401304bb10d1fda

FONT-100 (10172 bytes)
68d7cf5894cd8f8b87846f9c9cb70748027865cc3d37cbf27e1ef29e9419ce55

WIND-11500
de2204d3a092eb3a7f35d7ecbe0ec2379aa2bfdf0258e246b81ea61f0c762f47
```
