# 兩個輸入 bytes 對應單一中文字形：實機驗證

> 日期：2026-08-14  
> 前置文件：`re_15_text_byte_consumer_and_font100_runtime_lookup.md`

## 1. 結論

Dark Sun 原版 renderer 已成功完成第一個固定雙位元組映射實驗：

```text
輸入 bytes：47 6C                  ; ASCII "Gl"
映射 glyph：FONT-100 slot 0x40    ; 16×15「中」
原始畫面：Gladiators: Step forward, into the arena!
實測畫面：中adiators: Step forward, into the arena!
```

畫面只出現一個「中」，其後 `adiators` 緊接在正確位置，沒有多畫 `l`、沒有
多餘 advance，也沒有破壞後續 ASCII。這直接證明 renderer 可以在讀取 lead/trail
兩個 bytes 後只呼叫一次 glyph renderer，並只增加一次 16-pixel glyph width。

## 2. 測試策略

本次刻意不先處理 Big5 字庫 bank，也不修改 GPL 資源。測試句本來就以 ASCII
`Gl` 開頭，因此先把 `47 6C` 當作固定雙位元組碼，映射到已驗證的 FONT-100
slot `0x40`。

這樣可將實驗限制在控制流程本身：

```text
47 6C -> consume 2 bytes -> render glyph 0x40 once
```

若補丁只改 glyph index、沒有消耗 trail byte，畫面會多出 `l`；若 width 路徑
仍逐 byte 計算，置中或 layout 會保留兩個 glyph 的寬度。實測後續文字位置正確，
與補丁同時處理 renderer pointer 及 width pointer 的設計一致。

## 3. 補丁位置

本次測試版使用：

```text
scratch_test/font_16x15_experiment/DARKSUN/DSUN.EXE
```

原始檔備份：

```text
DSUN.EXE.dbcs-probe.bak
SHA-256 7bbd84f105b1ebe538a4abdfccdb2bacbf5b4fa763b45fa3a84499780f1d8c96
```

補丁後：

```text
SHA-256 3379d05fb05c90e4fbbe25b2b890373f2b58c996300b494e92ee2bb1138a5bd8
```

runtime code segment `36AA` 對應本次檔案基址 `0x33C60`。三個原本的
`mov al,es:[bx]`（`26 8A 07`）改成 same-segment near call：

| 用途 | runtime | file offset | patched bytes | helper |
|---|---:|---:|---|---:|
| 一般文字 renderer | `36AA:094A` | `0x345AA` | `E8 59 4A` | `36AA:53A6` |
| NUL 字串寬度計算 | `36AA:07F8` | `0x34458` | `E8 CB 4B` | `36AA:53C6` |
| `%s` 類格式字串 | `36AA:09A2` | `0x34602` | `E8 41 4A` | `36AA:53E6` |

helper 放在本次 code segment 內檔案與執行期均為零的測試空間；三份 helper
分別更新各函式自己的字串 pointer：

```asm
mov  al,es:[bx]
cmp  al,47h
jne  return
cmp  byte es:[bx+1],6Ch
jne  return
inc  word [bp+pointer_slot]  ; 額外消耗 trail byte
mov  al,40h                  ; FONT-100「中」
return:
ret
```

原函式返回後仍會執行既有的一次 pointer increment，因此 pair 總共前進兩 bytes。

補丁工具為：

```powershell
python tools/patch_dsun_dbcs_probe.py
python tools/patch_dsun_dbcs_probe.py --restore
```

工具會驗證所有原始 bytes、拒絕部分補丁狀態、建立一次性原始檔備份，並在寫入後
再次逐區驗證。

## 4. 啟動後驗證

測試版 DOSBox 重新啟動後，透過 debugger bridge 短暫暫停並讀回以下位置：

```text
36AA:094A OK
36AA:07F8 OK
36AA:09A2 OK
36AA:53A6 OK
```

確認磁碟補丁確實被載入記憶體後立即恢復執行。遊戲正常通過啟動、前段對話與
動畫，抵達目標句時成功顯示 `中adiators`，沒有當機。

## 5. 已證明與尚未證明

本次已證明：

1. renderer 可以把兩個輸入 bytes 解碼成一個 glyph index。
2. trail byte 可以由 renderer pointer 額外消耗，不會再被畫成第二個 glyph。
3. 16×15 glyph 只產生一次 width／advance，後續 ASCII 位置正確。
4. 一般文字、字串寬度與格式字串三個入口可共享相同解碼規則。
5. 修改後 DSUN.EXE 可正常啟動並走完目標動畫流程。

尚未證明：

1. 真正 Big5 lead/trail 範圍與所有 ASCII／`%` 控制碼的無衝突規則。
2. 超過 256 glyph 的外部 CJK font bank 或擴充 offset table。
3. 長中文句的自動換行、置中、MORE 分頁與裁切邊界。
4. 所有其他文字 renderer 是否都經過這三個入口。

## 6. 下一步

下一個最小里程碑應將固定 `47 6C -> 0x40` 擴展為真正的兩階段 lookup：

```text
ASCII byte             -> FONT-100 原槽位
合法 DBCS lead+trail   -> CJK glyph id / CJK font bank
```

在引入完整字庫前，先以少量測試 pair 驗證：

1. ASCII 與 DBCS 混排。
2. 行尾恰好放得下／差一 pixel 的換行。
3. 多頁對話的 MORE 與回頁。
4. `%` 格式參數前後的 DBCS。

其中第 1～3 項的第一輪實機驗證已由
`re_17_six_pair_dbcs_pagination_proof.md` 完成：六組連續 pair、ASCII 混排、
MORE 與回頁均正常。`%` 格式參數與精確 pixel 邊界仍待專門測試。
