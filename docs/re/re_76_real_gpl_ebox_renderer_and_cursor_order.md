# 真實 GPL/EBOX 對話 renderer 與 cursor 順序

日期：2026-09-13

## 結論

已在 v9 隔離 runtime 中，以第一個紀錄、眼睛 icon、門上方 NPC 成功觸發一般
GPL/EBOX 對話，並取得完整 renderer event trace。這不是模擬畫面，也不是 VIEW/UI
替代案例。

一般對話並非只用一套文字 renderer。同一個畫面同時包含：

1. `36AA:0864` `GgPrintString` 與 `36AA:06C0` `GgPrintFontCharacter`；
2. `GuiPrintString` 與 graphics `COUT`；
3. graphics `show_page`；
4. GUI cursor hide/show。

因此原生 Hires Text 不能只替換 `COUT` 或只攔 `draw_dot`。最合適的語意接點是兩個
`GgPrintString`／`GuiPrintString`；舊的 glyph／`COUT` raster output 則需抑制或替換。

## 可重現操作

第一個紀錄載入後的正確操作為：

1. 起始是箭頭 cursor。
2. 右鍵一次為嘴巴。
3. 右鍵第二次為眼睛。
4. 切換 verb mode 會把 cursor warp 到右側 action strip，因此必須再移回門上方 NPC。
5. 以左鍵點門上方 NPC。

bridge mouse id 為 `0=left, 1=right, 2=middle`。早期探測將 `1` 當左鍵，因此只切換
cursor，沒有觸發對話；該結果已排除。

## 探針與隔離

探針：

```text
D:\git\dsun-hires-text-poc\v9\probe_dialogue_renderer.py
```

完整事件：

```text
D:\git\dsun-hires-text-poc\v9\artifacts\dialogue-renderer-event-probe.json
```

畫面：

```text
D:\git\dsun-hires-text-poc\v9\artifacts\dialog-save01-after-npc-click.png
D:\git\dsun-hires-text-poc\v9\artifacts\dialog-save01-after-response-1.png
```

測試複製整個 v9 runtime 到系統 temporary directory，在該副本載入 SAVE01。原 v9
runtime、SAVE 與 `DSUN.EXE` 均未改寫；測試結束後 temporary directory 自動刪除。

執行期模組：

| 模組 | CS |
|---|---:|
| graphics | `11A4` |
| EBOX | `36AA` |
| cursor/GUI | `30F5` |

所有 action 均為 `truncated=false`。

## 初次開啟對話

計數：

| 事件 | 次數 |
|---|---:|
| `GgPrintString` | 22～24（不同執行輪的動態選項不同） |
| `GgPrintFontCharacter` | 376～396 |
| `GuiPrintString` | 1 |
| `COUT` | 16 |
| `show_page` | 2 |
| `GuiShowCursor` / `GuiHideCursor` | 各 4 |
| `GuiIShowCursor` | 22 |
| `GuiIHideCursor` | 11 |

`GuiPrintString` 的唯一呼叫為：

```text
xy=(6,4), "%C%C%C%s", "WHAT DO YOU SAY?"
```

它再逐字進入 `COUT`，正好 16 characters。

`GgPrintString` 負責：

- 上方 NPC 對話的已編碼行；
- 下方五筆回答選項；
- 每筆回答以 `%C%C%s` 格式取得完整 NUL-terminated string argument。

已直接從 stack 解出完整回答字串。GPL 在不同執行輪會提供不同的動態選項集合；
最新 artifact 的五筆為：

```text
Bravery comes easily from behind walls!
I won't work on Tectuktitlay's sandcastle.
If I die, I die.
I spit in the face of Tectuktitlay himself!
You will die by my hand!
```

相同行可能呼叫兩次，且建立過程中另有空字串／layout draw。Hires command queue 不可
單純把每次 formatter hit 都永久 append；必須依 surface/page、座標及 redraw epoch
取代舊 command 或去重。

## 選擇第一個回答

按鍵 `1` 後：

| 事件 | 次數 |
|---|---:|
| `GgPrintString` | 10 |
| `GgPrintFontCharacter` | 372 |
| `show_page` | 9 |
| `GuiShowCursor` / `GuiHideCursor` | 各 9 |
| `GuiIShowCursor` / `GuiIHideCursor` | 各 11 / 9 |

選項一完整字串在每次重畫仍可由 formatter argument 取得。之後 NPC 回應出現在上方
對話框。重複 redraw 並非新文字事件，進一步證明 queue 必須採 retained commands／
replace semantics，而不是 append-only overlay。

## Surface/page identity

每次 `GgPrintString` breakpoint 也讀取了 game globals：

```text
surface_id   = 3
front_page   = 0
back_page    = 1
dirty        = 1
```

同一句連續兩次 draw 的 surface/page state 完全相同，因此雙重 draw 不是一筆畫到
front page、另一筆畫到 back page。它是 EBOX 內部的雙 pass 或重建行為；對 Hires
queue 而言，至少可先用 `(surface_id, x, y)` 作 replace key。

初次建立對話內容時 `flip_enabled=0`。選項 1 的反覆動畫／重畫期間為 `1`，NPC 回應
重新建立時回到 `0`。這個 flag 應記錄在 redraw epoch，但不能單獨當作文字 identity。

## Cursor 與 page 的實際層級

選項動畫／重畫的重複核心順序為：

```text
GgPrintString
GgPrintFontCharacter x N
GuiShowCursor
GuiIShowCursor
show_page
GuiHideCursor
GuiIHideCursor
```

在這個特殊 page mode 中，文字先畫到底頁，cursor 再畫入即將顯示的頁面，之後才
page flip；換頁後清理 cursor backing。這與一般 `GuiUpdatePages` 的另一條 internal
hide/show 分支並不矛盾，而是 cursor state flag 不同。

對原生 Hires renderer 的直接要求：

```text
low-resolution game surface
  -> Hires Text for that surface/page
  -> cursor
  -> present/page flip
```

如果 Hires Text 在 `show_page` 之後才疊上去，會蓋住 cursor；如果只在 page flip
重畫，又會漏掉已證實不換頁的 hover。因此：

- `GgPrintString`／`GuiPrintString` 建立或更新 retained text command；
- surface dirty 或 direct visible update 觸發合成；
- `GuiShowCursor` 前完成 Hires Text raster；
- cursor 永遠最後畫；
- page flip 與直接 visible-surface update 都需支援。

## 下一步

1. 追 `MORE` 分頁，確認 command replace、cursor hover 與 page flip 的完整生命週期。
2. 做第一個遊戲內 renderer shim：只記錄 command queue，不改畫面；以 SAVE01 對話和
   VIEW hover 同時驗證 queue 不殘留、不重複。

## EBOX object lifecycle

依 DarkSunOnline 函式順序映射出的 16-bit 候選，已由本次 runtime breakpoint 正式
命中確認：

| runtime | 名稱 |
|---|---|
| `341D:07AB` | `GuiEBoxSetText` |
| `341D:085E` | `GuiInitEBox` |
| `341D:0AC1` | `GuiDrawEBox` |
| `341D:0B06` | `GuiKillEBox` |

初次開啟對話：

```text
GuiInitEBox x1
GuiDrawEBox x2
GuiEBoxSetText x1
GgPrintString / GgPrintFontCharacter
```

選擇回答 1 後：

```text
GuiEBoxSetText x1
GuiDrawEBox x1
GgPrintString / GgPrintFontCharacter
```

按 Esc 關閉：

```text
GuiKillEBox x1
cursor updates
show_page x1
```

關閉時 `GgPrintString=0`、`GgPrintFontCharacter=0`，畫面仍完整恢復世界，證明清除
不是靠 formatter 傳空字串，而是 EBOX destruction 加背景重建。

由此可定義第一版 retained queue lifecycle：

1. `GuiInitEBox` 建立 EBOX text scope。
2. `GuiEBoxSetText` 開啟新 redraw epoch／替換內容。
3. `GgPrintString` 以 `(scope, surface_id, x, y)` upsert text command。
4. `GuiKillEBox` 清除整個 scope。
5. `GuiPrintString/COUT` 屬於非 EBOX UI，使用另一個 scope/lifecycle。
