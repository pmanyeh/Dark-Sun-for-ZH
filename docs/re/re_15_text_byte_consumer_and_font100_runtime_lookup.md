# 文字 byte 消費迴圈與 FONT-100 執行期 lookup

> 日期：2026-08-14  
> 前置文件：`re_14_renderer_trace_checkpoint.md`

## 1. 結論

本次已由開場對話的 MORE／回頁操作，定位到真正的文字 renderer，並完成從
對話緩衝區到 FONT-100 字模像素的動態證明：

```text
對話字串
  -> 36AA:0864 格式化文字 renderer
  -> 36AA:0941 逐 byte 消費迴圈
  -> 36AA:06C0 單一 glyph 繪製
  -> FONT-100 offset table
  -> u16 width + width*height pixel bytes
  -> 11A4:2AF4 pixel draw
```

目前程式的字元模型已可確定為單位元組：一般路徑每讀一個 input byte，就呼叫
一次 `36AA:06C0`；字串寬度函式 `36AA:07E0` 也每次只前進一 byte。因此完整
DBCS 支援至少必須同步修改「繪製」與「寬度計算」兩條路徑。

## 2. 對話緩衝區與翻頁狀態

開場測試對話在不同階段出現過下列實體位址副本：

```text
第一段測試句：0x95D14、0x98850、0x99944
Gladiators 句：0x72B64、0x958E4、0x98494、0x990C4
```

其中 `0x98850` 可寫成 real-mode alias `9885:0000`。對該位址設 watchpoint 時，
先命中 `0824:1555 rep stosb`；這是在清除由 `97E9:0004` 開始、長 `0x1201`
bytes 的工作區，不是逐字寫入 renderer。

點擊 MORE 時，三份完整文字資料的雜湊均未改變。頁面內容是在同一份已組好的
文字緩衝區上切換，而不是重新複製下一頁字串。前頁按鈕造成的關鍵狀態變化為：

```text
EBOX object + 0x8A：5 -> 4
writer：341D:1811  mov es:[bx+008A],dx
redraw：341D:1821  call 341D:055D
```

`object+0x8A` 是可見起始行／捲動索引。另一個曾命中的 `object` button state
只是箭頭按鈕高亮，不是文字游標。

## 3. renderer 與逐 byte 迴圈

`341D:055D` 由 EBOX 的 line table 與可見行索引逐行重畫，最後呼叫
`36AA:0864`。真正讀取文字 byte 的一般路徑是：

```asm
36AA:0936  mov eax,[bp+0A]       ; far text pointer
36AA:093A  mov [bp-06],eax
36AA:0941  les bx,[bp-06]
36AA:0944  cmp byte es:[bx],25   ; '%' 格式控制碼
36AA:094A  mov al,es:[bx]        ; 讀取一個 input byte
36AA:094D  push ax
36AA:094F  call 36AA:06C0        ; 畫一個 glyph
36AA:09E1  inc word [bp-06]      ; 前進一 byte
36AA:09E4  les bx,[bp-06]
36AA:09E7  cmp byte es:[bx],00
36AA:09ED  jmp 36AA:0941
```

`%` 路徑會解析四種格式參數；其中字串參數仍在 `36AA:099F-09B5` 逐 byte
呼叫同一個 `36AA:06C0`，直到 NUL。

## 4. FONT-100 執行期結構

命中 glyph 函式時，全域 far pointer 為：

```text
[4B7A:A378] = 80E3:0004
physical    = 0x80E34
```

`80E3:0004` 起始的資料就是 FONT-100 payload：

```text
+0x000  u16 glyph_count = 256
+0x002  u16 height      = 15
+0x004  u32 runtime state/reserved
+0x008  u8  palette map[256]
+0x108  u16 glyph_offsets[256]
         glyph records...
```

載入器沒有把字模拆成未知的 protected-mode 結構。執行期的 13,888 bytes 與
`FONT-100.zh-16x15.bin` 相比只有三個 byte 不同：

```text
payload +0x006：00 -> 01
payload +0x01C：14 -> 11   (palette map[0x14])
payload +0x106：FE -> 2D   (palette map[0xFE])
```

offset table 與所有 glyph records 均保持不變。上述兩個 palette-map 改動也與
繪製迴圈以 pixel byte 查 `font+0x08` 的行為一致。

## 5. glyph lookup 與「中」的直接證明

`36AA:06C0` 的參數是單一 byte。lookup 核心如下：

```asm
36AA:06D3  mov al,[bp+06]
36AA:06D6  mov ah,00
36AA:06D8  shl ax,1
36AA:06DA  les bx,[A378]
36AA:06DE  add bx,ax
36AA:06E7  add dx,es:[bx+0108]  ; base + glyph_offsets[byte]
36AA:06FE  mov ax,es:[bx]       ; glyph width
36AA:0708  mov ax,es:[bx+02]    ; global height
```

測試 placeholder `@`（`0x40`，畫面顯示為「中」）的檔案與執行期資料均為：

```text
glyph_offsets[0x40] = 0x0FA9
runtime record      = 80E3:0FAD
physical record     = 0x81DDD
width               = 16
height              = 15
pixel bytes         = 240
pixel SHA-256        = 86803a6a319d9d34b269f7454d0181ecd130dfc1a9d2f870919ae1b03e4382f1
next record         = 80E3:109F
```

`0x0FA9 + 2 + 16*15 = 0x109B`；再加 runtime payload base offset `0x0004`，
下一筆位址正好是 `0x109F`。執行期 `@` record 與重封裝 FONT payload 完全
逐 byte 相同，排除了誤認其他圖形資源的可能性。

繪製函式在 `36AA:0761-07CB` 以 global height 與 glyph width 形成雙層迴圈，
從 record header 後讀取每個 pixel byte，經 `font+0x08` palette map 轉換後呼叫
`11A4:2AF4`，最後在 `36AA:07D1-07D7` 將游標增加 glyph width。因此 16-pixel
中文 advance 是 renderer 直接使用 FONT record width 的結果。

## 6. 字串寬度函式

`36AA:07E0` 是獨立的 NUL-terminated 字串寬度函式：

```asm
36AA:07F5  les bx,[bp+06]
36AA:07F8  mov al,es:[bx]
36AA:07FC  shl ax,1
36AA:080B  add dx,es:[bx+0108]
36AA:0819  add cx,es:[bx]       ; 累加 glyph width
36AA:081C  inc word [bp+06]     ; 前進一 byte
36AA:0822  cmp byte es:[bx],00
36AA:0828  mov ax,cx
```

這證明目前 width／layout 計算也以 byte 為字元單位。若只修改 `36AA:094A`
附近的繪製路徑，換行與置中寬度仍會把 DBCS lead/trail 當成兩個 glyph。

## 7. 下一個最小實驗（已由 re_16 完成）

下一步應使用一組不與 `%` 控制碼衝突的雙位元組測試值，先固定映射到現有
`0x40`「中」字模：

1. 在 `36AA:0941` 一般文字路徑辨識 lead byte，讀取 trail byte並只呼叫一次 glyph renderer。
2. 在 `36AA:07F5` 寬度路徑套用相同解碼，兩 bytes 只累加一次 16-pixel width。
3. 保留 ASCII、NUL 與 `%` 格式控制碼的既有語意。
4. 實機驗證下一個 ASCII 字元位置、置中／換行邊界與 MORE 分頁。

在建立正式 Big5 bank 前，固定映射實驗可先證明「兩 bytes -> 一 glyph」所需的
控制流程與 patch 空間。

實驗結果見 `re_16_two_byte_single_glyph_runtime_proof.md`：固定 pair `47 6C`
已成功只顯示一個 `0x40`「中」，畫面為 `中adiators...`，且後續 ASCII 未錯位。
