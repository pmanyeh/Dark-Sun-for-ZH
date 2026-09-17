# v59：檢視人物頁下移 3px、裝備格互動修復與多職業接續點

日期：2026-09-11

## 本次交付範圍

使用者接受 v58b 的兩欄三列能力值，但要求下移 2～3 個原生 pixels，並回報
右側直排裝備格無法右鍵開啟說明卡。另已確認後續中文排版必須考慮多職業。

本次先交付 **v59 互動修正版**：能力值下移 3px、排除隱藏控制項的命中區重疊。
尚未翻譯性別／種族／陣營、職業、EXP／HP／PSI／AC／DAM，也未搬動下半部分隔線。
不要把這個候選版當成整張屬性頁已中文化。

```powershell
& '.\scratch_test\cjk_display_staging_v59_view_interaction\launch-dosbox-x.cmd'
```

v58b 保留不動；新版本依 `build-view-interaction-manifest.json` 與 `V59-READ-ME.txt`。
繼承的舊版 notices／manifests 只記錄舊版本，不能當作 v59 驗收狀態。

## 1. 能力值

兩欄標籤／數字 X 仍為 149／177、201／229。
三列 Y 從 40、52、64 改為 **43、55、67**；10px 字高、12px 行距不變。
最後一列佔 Y=67～76，不碰原先 Y=86 的身分文字。

`assemble_name_slot_cache` 新增 `view_y_origin`，預設仍是 40，舊版本可重建。
只改 VIEW CHARACTER 的 FONT-local 座標常數，不改 EXE、不改全域字高。
背包頁與 v57 的單欄能力值路徑不變。

## 2. 裝備格失效的定位

三個真正的裝備控制項 `2BCFh..2BD1h` 在 v58b 的位置為
(259,42)、(259,61)、(259,80)，每格 18×18。

WIND-11500 還保留未顯示的 APFM 占位控制項，其中 `2BDC..2BDE` 位於
(262,42)、(262,62)、(262,82)，與新裝備格大幅重疊；`2BD6`／`2BDB`
位於 (243,62)／(243,82)，也會伸入裝備格左側 2px。
只挪走最顯眼的三個重疊格並不足以清空整個命中區。

v59 只修改此 WIND 的五組 placement：

| APFM | v58b | v59 |
| --- | --- | --- |
| 2BD6 | (243,62) | (241,62) |
| 2BDB | (243,82) | (241,82) |
| 2BDC | (262,42) | (205,42) |
| 2BDD | (262,62) | (224,42) |
| 2BDE | (262,82) | (241,42) |

真正裝備格的位置、ID、callback、事件遮罩都不動；不改共享 APFM chunks。
建置與測試會逐一檢查 `2BCD..2BE1` 小型裝備占位區，拒絕任何仍與真正裝備格
相交的位置。此檢查不宣稱涵蓋所有任意形狀或事件遮罩的視窗控制項。

原說明卡 callback 在 EXE `0x8A8D5`，右鍵分支 `0x8A95B`：它以控制項 ID
查詢矩形，並讀取 `DS:9CEC[SI]` 的物品 ID；`FFFFh` 表示空格。
卡片呼叫在 `0x8A9AF`，並沒有需要同步修改的固定三格座標。
實際載入 GERAKIS 時，三格物品 ID 為 FFFF、0、1；名稱 ID 為 FFFF、001C、0011。

## 3. 驗證與限制

- 130 項單元／Unicorn 機器碼測試通過，無 skip。包含新座標的標籤與數字
  formatter 參數、stack／暫存器保存，以及既有背包／能力值／名稱流程。
- v58b FONT 核心重建吻合；v59 EXE 完全不變，沒有新增 relocation。
- RESOURCE 的 1205 chunks 中，只修改 FONT-100、WIND-11500。
  1202 個非目標內容一致，GFFI-1 僅作容器 metadata 例外；81 個其他父版檔案一致。
- DOSBox-X A/B 使用同一個存檔 `0001`、同一 bridge 輸入條件。
  v58b 在 GERAKIS 第二格中央右鍵未出卡；v59 第二格顯示 Bone 長劍，
  第三格顯示 Wooden 棍棒，切換 K’Ratchek 後第一格顯示 Obsidian 武器說明卡。
- v59 切換到 K’Ratchek 後，三職業 Fighter/Druid/Psionic 與 2/2/2 仍顯示，
  中間職業／等級保留原紅色。本版沒有更動職業或其數值。
- 自動測試啟動額外使用 `-set "sdl mouse_emulation=always"`，**只在測試程序命令列**。
  這讓 bridge 絕對座標不被主機游標位置覆寫；未改候選版設定或使用者 launcher。
  初次沿用預設滑鼠模式的 bridge 未能可靠派送點擊，不能拿該結果判斷遊戲 callback。
- bridge 擷取仍有右半重複／條紋的既有問題；只能作互動與內容 smoke test。
  最終正式視窗排版、游標捕捉／切換焦點的體驗仍由使用者確認。
- VIEW CHARACTER 底部 hover 名稱仍有未接入 NAME-slot 解碼的路徑
  （`0x8A925` 附近）；自動測試看見非正常名稱字串。這不是本次右鍵修復的完成項，
  下一步應接入解碼，不能宣稱所有 hover 中文均已正常。
- 本次未存檔、未 commit／push；測試結束只關閉本次建立的 DOSBox 程序。

建置 manifest 的 `not_run` 是可重建的產出時狀態；上述是產出後另行完成的實機測試。

## 4. 接續中文排版：保留多職業需求

已同意的方向，不是本版已實作內容：

1. 性別、種族、陣營合併為一列；以最長譯名實測寬度，避免右側裝備格。
2. 職業固定預留兩列。每個「職業＋等級」視為不可拆的單位，第一列放兩職，
   第三職放第二列；單職也保留第二列高度，避免不同人物的下方欄位跳動。
3. 保留每個職業與其等級的對應及原有顏色，不把獨立的 `2/2/2` 任意合併錯序。
4. 下半部目標是五列：兩列職業、經驗一列、生命／靈能一列、防禦／傷害一列。
   漢字字高至少 10px，必要時先上移分隔線，不能只把舊 7px 行距直接換中文。
5. 最大三職、最長職業譯名、多位數等級、大經驗值與長傷害式都要納入版面測試。
   「目前經驗（門檻）」的門檻來源／多職業選取邏輯仍須追查，不先臆定計算語意。

下半部既有呼叫定位：

| 內容 | VIEW 呼叫位置 | 原座標 |
| --- | --- | --- |
| 性別／種族 | 0x8A1AC | (149,86) |
| 陣營 | 0x8A1DC | (149,93) |
| 職業 | 0x8A20E → 0x8A8B4 | (149,106) |
| 等級 | 0x8A23C | (149,113) |
| 經驗資料準備／顯示 | 0x8A279／0x8A298 | (149,120) |
| HP 標籤／數字 | 0x8A2C7／0x8A30E | (149,127)／(189,127) |
| PSI 標籤／數字 | 0x8A33D／0x8A384 | (149,134)／(189,134) |
| AC／DAM | 0x8A3B9／0x8A3D2 | (149,141)／(199,141) |

每個新 EXE hook 都必須通過 v58b 引入的 overlay relocation overlap guard，
不可再把尚未 relocated 的 segment 常數複製進 FONT 核心。

## 5. 重建與 hashes

```powershell
python tools/build_view_interaction_candidate.py --output scratch_test/v59_rebuild_check
$env:PYTHONPATH = (Resolve-Path scratch_test/ui_emulation_deps).Path
python -m unittest discover -s tests
```

```text
DSUN.EXE（與 v58b 相同）
9ac8f29f1a9525ca7f54a768a8c5501e23d8b22812e3c28275c8e09891b61990
RESOURCE.GFF
e90624c5a677f8de3191ea9d68a493d19e7654c2a2bd5127510de237a9b156ef
FONT-100（10172 bytes）
4636654eea8243c6b81ee57e14406f0bd7a3d86dc684dd784d6c2bfadb7c34d9
WIND-11500
5c77728847caf0ead41706fb9241eb70e221f9f7acadc15cceb9941ddc71c1f4
```
