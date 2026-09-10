# v52 物品 10px 格線與右側溢出 checkpoint

> 日期：2026-09-10
>
> 狀態：v52 已由使用者實機確認主要文字不再重疊；右側多武器溢出與殘影尚未解決。

## 1. 本輪結果

物品名稱的七個動態 FONT slots 改用可列印 transport codes：

```text
22 23 26 3C 3E 5C 7E
```

此設計可正常 Load Game、開啟物品欄、顯示右鍵說明卡與右側攻擊資訊。
滑鼠設定必須維持 `autolock=false`。首次取得焦點後右鍵偶爾不送入遊戲；切到其他
視窗再切回即可恢復。使用者明確要求不要改成自動捕捉。

## 2. 已否決的行高方案

- v46 在 `339E:02F0` 的 `%s` draw call 後把 `DI` 改成 10。原始 renderer 已把
  內部座標推進 10；此修補只改 bookkeeping，畫面沒有可見改善，因此撤回。
- v47 把 `36AA:0704` 的 glyph-height call 導入 FONT-local helper。Load Game
  在 FONT pointer 尚未可用時會走這條路，點 Load 立即閃退。
- v48 把 legacy helper `36AA:53D6` 導向常駐 per-code helper；Load Game 仍立即
  閃退。結論與 v39 一致：不得修改這條全域 height query。

目前 source 與 v52 已完整撤回 v47/v48 的 height hook。

## 3. 說明卡局部格線

右鍵說明卡的 NAME consumer 位於 file offset `0x072955`，執行期 inner formatter
caller 為 overlay-local `2B9C`；數值列 caller 為 `2CD4`。

```text
0x07296F  83 46 0E 07 -> 83 46 0E 0A
```

v49 起把整列增量改為 10。使用者確認說明卡中的 `Bone / 長劍 / 1D8-1` 已不再
重疊。這是整列格線，不依當下文字是否已翻譯；將來 `Bone -> 骨製` 應沿同一
10px 格線排列。

## 4. 右側欄實際座標證據

在共用物件文字 wrapper `2143:0A40` 設 breakpoint，直接讀取呼叫 stack，取得
v50 的實際 Y：

```text
第一武器 NAME       120
第一武器數值        130
第二武器 NAME       134
第二武器數值        144
```

inner line advance 已是 10，但 outer block stride 仍是兩行乘 7，即 14：

```text
file 0x072771  8B D0             mov dx, ax       ; inner 回傳行數
file 0x072773  6B C0 07          imul ax, ax, 7
file 0x072776  01 46 0E          add [bp+0E], ax  ; 下一區塊起點
```

v51 將 multiplier 改為 10。使用者確認兩件武器之間已留出正確間隔；格線成為
`120,130,140,150`。

## 5. AC 到武器區塊

`AC:` 字串在 DGROUP `0x0E60`，繪製 call 位於 file `0x064DAF`。右側主函式中：

```text
file 0x06F61A  packed x/y = 00EC:0063  ; AC: 8，Y=99
file 0x06F6A5  packed x/y = 00EC:0078  ; 武器區起點，Y=120
```

原差距 `120-99=21=3*7`。v52 把 `0x06F6A5` 的 Y 由 `0x0078` 改為
`0x0081`，使差距成為 `129-99=30=3*10`。使用者回報此版排列「很好」。

## 6. v52 的局部 layout patches

`tools/plan_name_slot_consumers.py` 的 `ITEM_LINE_ADVANCE_PATCHES` 現含：

```text
0x06F6A5  weapon section Y: 0x78 -> 0x81
0x072773  outer item block multiplier: 7 -> 10
0x07296F  item-card/name row: +7 -> +10
0x08BE7C  right-panel conditional row: +7 -> +10
0x08BF3A  right-panel conditional row: +7 -> +10
0x08C07D  right-panel detail row: +7 -> +10
0x08C0FB  right-panel detail row: +7 -> +10
0x08C132  multi-line multiplier: 7 -> 10
```

後五處屬同一個右側資訊 overlay；目前測試物件的主要可見改善由
`0x072773` outer multiplier 與 `0x06F6A5` section origin 證實。不可只依靜態
位置推論 conditional branch 已被實際執行。

## 7. v52 build checkpoint

```text
scratch_test/cjk_display_staging_v52_ac_item_grid

DSUN.EXE SHA-256
ebb7418af697251bc22e64f43fde0533bf3c53c344ffb3d139e1278c7de14a98

RESOURCE.GFF SHA-256
d42018652b79f4231baa70610235fcded048520a4aa3cfaf419849c07b527470

FONT-100 bytes  9768
FONT core bytes   653
```

離線測試為 `42 passed, 7 subtests passed`。GFF 驗證 1205 chunks；1 個目標 FONT
chunk 改變，1203 個 non-target chunks 不變，另允許 GFFI container metadata
更新。主 MZ relocation table 沒有新增項目。

## 8. 新 blocker：種族自帶武器造成下緣溢出與殘影

使用者在 v52 切換到有「種族自帶武器」的角色後確認：右側除裝備武器外，還會
額外列出 innate/racial weapon。兩種以上的攻擊區塊使用 10px 格線後會突破右側
面板下緣。接著切換角色，越界畫出的 pixels 不在原版重畫／清除矩形內，因此殘留
在底部按鈕區，形成殘影。

這不是單純再加行距即可解決；下一輪必須同時處理 layout capacity 與 invalidation。

## 9. 下一 Session 的建議順序

1. 以 v52 為唯一基準，不回到 v47/v48 global-height 路線。
2. 使用有 innate weapon 的角色重現三個以上 attack blocks，記錄每個 block 的
   `2143:0A40` Y、回傳行數與最終 bottom Y。
3. 找出右側面板的合法 clip/clear rectangle，以及角色切換時實際清除的 bottom。
4. 先修殘影：角色切換／右側重畫前清除完整面板區，或對文字套用合法 clip。
5. 再決定 overflow layout：可考慮超量時使用 compact profile、縮小區塊間空白，
   或分欄／分頁；不要直接恢復全域 7px，否則中文又會重疊。
6. 測試矩陣至少包含：無武器、一件武器、雙持、種族自帶武器＋一件裝備、種族
   自帶武器＋雙持，以及在這些角色之間反覆切換確認無殘影。

## 10. Debugger 收尾

本輪 `2143:0A40` breakpoint 已移除；最後確認 breakpoint list 為空，guest 為
`running=true`。目前啟動的是 v52，滑鼠 `autolock=false`。

