# 原生 Hires Renderer：中央輸出層定位 checkpoint

日期：2026-09-13

## 目標與限制

目標是讓原始 `DSUN.EXE` 自己支援高解析輸出，不修改或維護特製 DOSBox-X。

本階段只定位邊界，尚未修改遊戲執行檔。

## 已證實的結論

遊戲沒有唯一的「最後一個畫面輸出函式」。`show_page` 只負責換頁；部分 UI（例如裝備 hover）會直接畫到目前可見頁面，因此不一定經過 `show_page`。

真正可利用的中央邊界是一整個集中式 graphics driver 模組。上層 GUI 多半以 surface 編號和邏輯座標呼叫它，VGA segment、plane mask、stride 與 clipping 都集中在這個模組內處理。

這表示可行方向是：保留遊戲邏輯與 GUI 呼叫，替換底層 graphics driver，讓它畫到新的軟體 framebuffer，再由遊戲本身送到 VESA 畫面。這不需要修改 DOSBox-X。

## DSUN.EXE 圖形函式對照

靜態檔案位址與執行期 `11A4` segment 的對照如下：

| 名稱 | 靜態位址 | 執行期位址 | 狀態 |
|---|---:|---:|---|
| `set_video_mode` | `0x11573` | `11A4:2973` | 已由指令內容及上游符號共同確認 |
| `draw_dot` | `0x116F4` | `11A4:2AF4` | 已確認 |
| `read_dot` | `0x11818` | `11A4:2C18` | 已確認 |
| `draw_line` | `0x11944` | `11A4:2D44` | 已確認 |
| `draw_rect` | `0x1208C` | `11A4:348C` | 已確認 |
| `fill_rect` | `0x1222A` | `11A4:362A` | 已確認 |
| surface setters/getters | `0x12E3F` 起 | `11A4:423F` 起 | 函式順序已對上 |
| `GET_BUFFER_SEGMENT` | `0x12FAE` | `11A4:43AE` | 已確認 |
| `my_copy_window` | `0x13323` | `11A4:4723` | 已確認 |
| `show_page` | `0x14414` | `11A4:5814` | 靜態與 runtime breakpoint 均已確認 |
| `COUT` | `0x145C1` | `11A4:59C1` | 已由上游符號順序及函式內容確認 |
| 已知 RLE/image renderer | `0x1532A` | `11A4:672A` | 既有 runtime trace 已確認 |

命名比對來源：DarkSunOnline 的公開 `tools/symbols.txt` 與 `tools/mdark.bin`。32-bit port 的函式排列與本遊戲 16-bit graphics segment 高度一致；關鍵函式的硬體操作也逐條相符。

來源：https://github.com/greg-kennedy/DarkSunOnline/blob/master/tools/symbols.txt

## 已解出的 ABI

這些函式是 far call；`BP+6` 是第一個參數。

```c
draw_dot(surface_id, x, y, color);
read_dot(surface_id, x, y);              // AX 回傳顏色，越界時為 FFFFh
draw_line(surface_id, x1, y1, x2, y2, color);
draw_rect(surface_id, x1, y1, x2, y2, color);
```

`draw_dot` 與 `read_dot` 都先做 surface clipping，再由 surface descriptor 取得實際 segment、原點與 stride。目前的 VGA 實作最後才轉成四-plane 位址並寫入 `03C4h/03CEh`。

`draw_rect` 也使用相同 descriptor；它會裁切矩形後逐列寫入目的 surface。

## Surface descriptor

graphics segment 內有多組以 `surface_id * 2` 索引的 word array：

| CS 位移 | 已觀察用途 |
|---:|---|
| `0004h` | destination segment，或 linked surface 的下一層索引 |
| `0204h` | buffer/配置相關欄位 |
| `0404h` | X1 |
| `0604h` | Y1 |
| `0804h` | X2 |
| `0A04h` | Y2 |
| `0C04h` | flags；`0040h` 表示 linked/sub-surface |

每個 primitive 都先把目前 descriptor 正規化到 `CS:0E04h` 起的 scratch fields，再進行 clipping 與繪製。這是可替換 renderer 的主要接縫。

## 文字並非只有一條 raster path

目前至少有兩條：

1. GUI formatter / glyph path：既有 runtime trace 為 `36AA:0864 -> 36AA:0941 -> 36AA:06C0 -> draw_dot`。
2. graphics module 的 `COUT`：接收單一字元，但會直接操作 VGA plane 並寫 glyph bytes，沒有呼叫 `draw_dot`。

所以只攔 `draw_dot` 不能涵蓋所有文字。原生 Hires Text 至少要攔截 GUI 的語意文字路徑以及 `COUT`，或把整個 graphics driver 改成不再直接碰 VGA。

## 換頁與滑鼠層級

`GuiUpdatePages`（靜態 `0x347B7`）的順序已確認：

1. 判斷 dirty、front/back page 與 page-flip enable。
2. 隱藏／暫存目前 cursor。
3. 呼叫 `show_page(-1)`。
4. 執行頁面切換後的更新。
5. 重新顯示 cursor。

因此正常 page flip 的 cursor 層級是受控的。但 hover 更新已實測可在零次 `show_page` 的情況下改變可見畫面；新 renderer 不能把 present 只掛在 `show_page`。

建議新 renderer 的合成順序為：

1. 低解析遊戲世界/UI framebuffer。
2. queued Hires Text。
3. mouse cursor（最後一層）。

所有 graphics primitive 應標記 dirty rectangle；直接更新與 page flip 都必須能觸發 present。這樣可避免文字與游標互相覆蓋，也能涵蓋 hover。

## 建議的第一個真實原生試驗

不要一開始全面換成 VESA。先做一個最小、可回退的 renderer shim：

1. 保留現有 Mode X 初始化與所有原始圖像繪製。
2. 在 GUI 語意文字入口捕捉字串、位置、顏色與 clipping window。
3. 暫時仍讓原字型照常畫，先證明遊戲內能建立正確的 Hires text command queue。
4. 把 queue、cursor hide/show、page flip、hover direct update 的事件順序記錄出來。
5. 順序穩定後，才加入 VESA framebuffer、抑制原字型，並把 Hires 字形放在 cursor 之下。

這一步會開始改動遊戲的繪製程式，但範圍限於可控的 renderer shim；不需要任何特製 DOSBox-X。

## 下一個待證項目

- 列出 graphics segment 中所有直接寫 VGA/VRAM 的函式，避免漏掉繞過 primitive 的路徑。
- 對一般對話、hover、角色頁、物品卡與 cursor 移動分別記錄文字入口和 present 事件。
- 確定 16-bit DOS 可用的 buffer 配置策略（conventional memory、EMS/XMS 或 VESA banked VRAM）。
- 在目標環境查詢 VBE mode，而不是假定固定 mode number。

## Runtime renderer event probe（2026-09-13）

新增唯讀探針：

```text
D:\git\dsun-hires-text-poc\v9\probe_renderer_events.py
```

它只在私人 DOSBox-X 測試程序設定 code breakpoints、讀 CPU/stack；不寫 guest
memory，也不修改 runtime 遊戲檔。完整結果位於：

```text
D:\git\dsun-hires-text-poc\v9\artifacts\renderer-event-probe.json
```

本次每個 action 都在 idle 前收完全部事件，`truncated=false`。

### 執行期模組位址

- graphics CS：`11A4`
- cursor/GUI CS：`30F5`
- relocation load segment：`0824`

四個 cursor 函式已由函式內容及 DarkSunOnline 符號排列正式對上：

| runtime | 名稱 |
|---|---|
| `30F5:093D` | `GuiIShowCursor` |
| `30F5:0B7F` | `GuiIHideCursor` |
| `30F5:0DE0` | `GuiShowCursor` |
| `30F5:0E0B` | `GuiHideCursor` |

### VIEW 實測計數

| 動作 | bitmap | formatter | COUT | show_page | 其他重點 |
|---|---:|---:|---:|---:|---|
| 進入 VIEW | 105 | 36 | 56 | 1 | cursor internal hide/show 多次 |
| 切換角色 2 | 39 | 37 | 65 | 1 | `draw_rect` 1 次 |
| 裝備 hover | 1 | 1 | 17 | **0** | `draw_rect` 1 次 |
| 物品卡 mouse-down | 1 | 0 | 0 | 0 | 尚未換頁 |
| 物品卡 mouse-up | 2 | 0 | 0 | 1 | 放開按鍵時才換頁 |
| 關閉物品卡 | 120 | 0 | 0 | 2 | 大量重建 bitmap |
| 離開 VIEW | 43 | 0 | 0 | 1 | 返回遊戲世界 |

### Hover 的完整關鍵順序

滑鼠移至空手裝備格時，完整事件為：

```text
GuiIHideCursor
GuiIShowCursor
draw_bitmap
draw_rect
resident_formatter(x=113, y=176, "%C%C%C%s", "NO WEAPON IN HAND")
COUT x 17
```

期間完全沒有 `show_page`。這同時證明：

1. hover 是直接更新 visible surface；
2. 這條真實 UI 路徑會先經 resident formatter，再逐字進入 `COUT`；
3. cursor 已在 hover 文字 rasterize 前重新顯示。

原 UI 因 hover 文字固定在畫面底部、cursor 位於裝備格，兩者通常不相交，因此沒有
立即出錯。但 Hires Text 若改變 glyph 大小、行寬或位置，不能依靠這個空間上的巧合。
新 renderer 必須保存語意文字 command，並以「低解析畫面 → Hires Text → cursor」
重新合成。

### 一個額外重要結果

進入 VIEW 與切換角色都同時大量命中 resident formatter 和 `COUT`。所以兩者不是
互斥的兩套畫面，而是這條 VIEW UI pipeline 中的不同階段。resident formatter 是
較適合捕捉完整文字語意的位置；`COUT` 則是必須抑制或替換的舊低解析 rasterizer。

這個 resident formatter 位於靜態 `0x30D0D` 一帶，不能與既有 EBOX runtime trace
中的 `36AA:0864` 混為同一函式。一般 GPL/EBOX 對話已知走
`36AA:0864 -> 36AA:0941 -> 36AA:06C0 -> draw_dot`；仍須用本次多 breakpoint
探針實測一次完整對話及翻頁，補齊 cursor/page 事件順序。

此項已由 `re_76_real_gpl_ebox_renderer_and_cursor_order.md` 完成：SAVE01 真實對話、
五筆回答、選項 1 後續回應與 cursor/page 次序均已取得完整 runtime trace。
