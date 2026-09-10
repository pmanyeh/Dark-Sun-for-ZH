# FBOV/VROOMM overlay relocation 格式解密與 DS-relative 間接呼叫設計

## 1. 背景

`re_54` 第 7 節記錄了 v36（NAME-1 物件 renderer 直接 far call 方案）在實機被拒絕：
把 4 個 consumer 的 segment word 加進主 EXE 的 MZ relocation table 後，DOSBox-X
啟動時整個畫面變黑，還原回 v33 才恢復正常。當時只知道「這 4 個 consumer 位於
動態 overlay」，但不知道 overlay 真正的 relocation 機制長什麼樣子。

本文件記錄：找到並解碼 Borland FBOV/VROOMM overlay 格式、確認 v36 失敗的精確
根因、以及一個不需要碰任何 relocation table（無論主 MZ 表或 FBOV fixup 表）的
新間接呼叫設計。**本輪全程只讀取 `DSUN.EXE`，未做任何寫入或建版。**

## 2. FBOV/VROOMM 格式（來源與結構）

透過 WebSearch 找到 Ghidra 外掛
[`GeReV/ghidra_scripts/LoadBorlandOverlays.java`](https://github.com/GeReV/ghidra_scripts/blob/main/LoadBorlandOverlays.java)
（GitHub raw 內容一度被 rate-limit，改用 jsdelivr CDN 鏡像
`https://cdn.jsdelivr.net/gh/GeReV/ghidra_scripts@main/LoadBorlandOverlays.java`
才抓到），完整逆向出 Borland TLINK overlay（FBOV，即 VROOMM）的二進位格式：

```
MZ header
  -> BorlandMzExtension（緊接在 MZ header 之後；magic 0xFB，版本 nybble）
  -> BorlandFileHeader（"FB","OV" magic；位於 (loaded_size+15)&~15；
       欄位：size, stofs=__SEGTABLE__ 的檔案位移, nsegs=筆數）
  -> BorlandSegmentEntry[nsegs]（__SEGTABLE__；每筆 8 bytes：
       seg（連結期 pseudo-segment）, maxoff, flags（CODE=1/OVR=2/DATA=4）, minoff）
  -> 每個 flags 含 OVR 的 entry，在 (header_bytes + entry.seg*16) 有一份
       BorlandOverlayHeaderRecord（32 bytes）：
         fileofs（相對 FBOV header 結尾的檔案位移）、codesz（overlay 程式碼大小）、
         fixupsz（fixup table 大小，緊接在程式碼後面，每筆 2 bytes）、
         jmpcnt（trap stub 數量，緊接在此 header 後面，每筆 5 bytes：
                 int 3Fh + offset + pad —— 這正是 re_08 觀察到的
                 「int 3Fh 呼叫樁／動態填值遠跳分派表」機制的磁碟原型）
```

**Fixup（relocation）演算法**（來自該腳本第 339-354 行，經與 `DSUN.EXE` 實測比對
完全吻合）：

```
for each fixup_offset in overlay.fixups:
    sf = 該 overlay 程式碼在 fixup_offset 處目前存的 16-bit 值（占位符，非真正 segment）
    idx   = sf >> 3       # __SEGTABLE__ 的索引
    flags = sf & 7        # bit0 = FIXUP_FUNREF
    real_segment = __SEGTABLE__[idx].seg + program_load_base
    把 real_segment 寫回 overlay 程式碼的 fixup_offset 處
```

也就是說：**overlay 程式碼裡看到的「segment」欄位，在磁碟上其實是
`(segtable_index << 3) | flags` 這種占位編碼，只有在該 overlay 被載入時，
由遊戲自己的 overlay manager（不是 DOS loader）巡覽這份私有 fixup 清單才會被
改寫成真正的 runtime segment。**

## 3. 對 `DSUN.EXE` 的實際靜態解析結果

```
MZ header:  cparhdr=0x540 -> header_bytes=0x5400
loaded_size（DOS 標準載入模組大小）= 0x52EA0
FBOV header @ 0x52EA0，stofs=0x46770，nsegs=220
```

`__SEGTABLE__` 220 筆裡：

- entry[0..80]：純 `CODE`，seg 由 0x0000 升到 0x3653 —— 這些是**靜態常駐**程式碼，
  屬於 DOS 標準載入模組，走一般 MZ relocation。
- entry[81..144]：flags=0（未分類的靜態資料/尾端）。
- entry[145..149]：`DATA`。
- entry[150]：`CODE`（無 OVR）。
- entry[151..208]：`CODE+OVR` —— **這些才是真正的 FBOV 動態 overlay 單元**，
  對應到 `header_bytes + entry.seg*16` 各自的 `BorlandOverlayHeaderRecord`。
- entry[209]：`seg=0x4356`，`maxoff=0xa4bc`，flags=0 —— 就是 **DGROUP**（見第 5 節）。
- entry[210..219]：`DATA`／收尾。

4 個已知 NAME-1 consumer 對應到的 overlay 單元：

| consumer file offset | `__SEGTABLE__` index | overlay seg | overlay code 範圍 | fixupsz | jmpcnt |
|---|---|---|---|---|---|
| `0x06E288` | 175 | `0x4265` | `0x6BD80..0x6F8F3` | 1114 bytes（557 筆） | 33 |
| `0x072955` | 176 | `0x4272` | `0x6FDD0..0x731F0` | 774 bytes（387 筆） | 40 |
| `0x08BECF` | 200 | `0x4324` | `0x8AEE0..0x8C7E4` | 382 bytes（191 筆） | 10 |
| `0x08BF00` | 200 | `0x4324` | 同上 | 同上 | 同上 |

實際反組譯確認：這 4 處後面既有的 far call（例如 `0x072955` 後面的
`LCALL 0090:0A40`）其 segment 欄位（`0x0090`／`0x00A0`／`0x00A8`）都**不在**
主 MZ relocation table 裡；換算成 `sf>>3` 分別是 18、20、21——正是
`__SEGTABLE__` 的索引，完全符合上面的 fixup 演算法。

## 4. v36 失敗根因（已精確定位，非推測）

`CODE_BASE`（`0x33C60`，我們的 resolver／cache／解碼器所在位置）本身落在
`loaded_size`（`0x52EA0`）**之內**，對應 `__SEGTABLE__[49]`（`seg=0x2E86`，
flags 只有 `CODE`，沒有 `OVR`）——它是**靜態常駐** segment，這也是為什麼
`patch_dsun_scratch_cache.py` 長期用 `header_bytes+segment*16+offset` 直接寫入、
且透過主 MZ relocation table 定位它一直都正確無誤的原因。

但 4 個 NAME-1 consumer 全部落在 `loaded_size` **之外**，屬於真正的 `FBOV_OVR`
動態 overlay。v36 把新的 relocation 加進主 MZ 表、指向這些 consumer 的 segment
word 時，DOS loader 用 `header_bytes+segment*16+offset` 換算出的目標位址，
其實遠遠超出**實際被載入的靜態影像大小**——overlay pool 從未被當成 DOS 標準
載入模組的一部分載入。這筆「relocation」等同於指示 DOS loader 去修補一段
從未配置、或早已被其他用途佔用的記憶體，這正是造成開場全黑畫面的根本原因。

**結論：對 4 個 consumer 而言，唯一結構正確的兩條路是（a）把新 fixup 項目插入
它們各自 overlay 單元的私有 fixup table（檔案結構外科手術，風險最高），或
（b）完全不透過任何 relocation 機制，執行期用已知的固定 segment 差值自己算出
目標 segment。本文件採用 (b)。**

## 5. DS-relative 差值設計（已交叉驗證）

程式進入點（連結期 `CS:IP = 0000:0000`，檔案位移 `0x5400`）反組譯：

```
0x005400: mov dx, 0x4356      ; 這個 word 有登記在主 MZ relocation table
0x005403: mov word ptr cs:[0x2c4], dx
...
0x005414: mov ds, dx
```

`0x4356` 正是 `__SEGTABLE__[209]`（DGROUP）的連結期 segment，且與其
`maxoff=0xa4bc` 吻合 DGROUP 實際大小（換算檔案範圍 `0x48960..0x52E1C`，
非常接近 `loaded_size=0x52EA0` 的邊界）。因此：

```
CODE_BASE 連結期 segment（0x2E86）− DGROUP 連結期 segment（0x4356）= −0x14D0
=> CODE_BASE 的 runtime segment = DS(runtime) − 0x14D0
```

**交叉驗證**：`re_08` 記錄某次中斷點 `DS = 4B7A`；`re_54` 記錄同一類 v33
session 裡 CODE_BASE 的 runtime segment觀測值是 `36AA`。代入公式：
`0x4B7A − 0x14D0 = 0x36AA`，**完全吻合**，證明這個差值是這個 build 內固定的
連結期常數，執行期用 `DS` 反推絕對正確，且不受每次啟動的載入位置變動影響。

## 6. 呼叫端 byte 預算與最終指令設計

4 個 consumer 現場原本的 14-byte `NAME_POINTER_SEQUENCE`
（見 `tools/plan_name_slot_consumers.py`）要被等長替換。若沿用舊設計
（`consumer_redirect_bytes()`：直接 far call + 呼叫端 `push dx; push ax`
收尾），新版因為要先算 `DS-0x14D0` 再間接呼叫，指令長度會變成 16 bytes，
超出預算 2 bytes。

**已算出的最省 byte 版本**（呼叫端，4 處共用同一段位元組）：

```
MOV BX, DS            ; 8C DB              (2 bytes)
SUB BX, 0x14D0         ; 81 EB D0 14        (4 bytes)
MOV [mem_seg], BX      ; 89 1E xx xx        (4 bytes)  <- mem_seg = 暫存格+2
CALL FAR PTR [mem_off] ; FF 1E xx xx        (4 bytes)  <- mem_off = 暫存格開頭
                                             合計 14 bytes，剛好等於原本長度
```

`mem_off` 處的 offset word（解碼器入口 `DECODER_OFFSET=0x51F1`）在**建置時**
就先烘焙好、永遠不變；執行期只需要覆寫 `mem_seg` 那個 word。

原本設計裡呼叫端收尾的 `push dx; push ax`（把解碼器回傳的 `DX:AX` 遠指標
留在堆疊上供後續原始碼消費）**搬進解碼器自己的返回序列**，改用堆疊重排：

```
; 於 tools/cjk_name_slot_cache.asm 的 cache_return 內，原本：
;   pop es / pop ds / pop di / pop si / pop cx / pop bx / pop bp
;   mov ax, name_buffer / push cs / pop dx / lret
; 改為在 lret 之前插入：
    pop cx            ; cx = 遠呼叫的返回 IP
    pop bx             ; bx = 遠呼叫的返回 CS
    push dx            ; 先推 segment（較深）
    push ax             ; 再推 offset（頂端）—— 順序與原始「push segment; push dx」相同
    push bx             ; 還原返回 CS
    push cx              ; 還原返回 IP
    retf                 ; 回到呼叫端下一條指令，堆疊上已經是 [offset, segment, ...]
```

只多 6 bytes，解碼器目前 391 bytes、cave 還有 42 bytes 空間，塞得下。

**如此一來，呼叫端 4 處全部剛好用滿 14 bytes，不需要更動任何一個 byte 的長度、
不影響後續原始指令的相對位置，也完全不需要新增任何 MZ 或 FBOV relocation。**

## 7. 唯一未解問題：暫存記憶格必須在 DGROUP（DS-relative），位置未定

`MOV [mem],BX` 與 `CALL FAR [mem]` 若要維持上面 4-byte 的精簡編碼，記憶體
運算元必須用「純位移、預設 DS」定址（省略 segment override 前綴）；一旦改用
`CS:` override 會各多 1 byte，總長度變 16，又超預算。這代表 4-byte 暫存格
**必須落在 DGROUP（DS 相對位址空間）**，不能沿用我們完全掌控的 `CODE_BASE`
cave。

對 DGROUP（連結期 `0x4356`，檔案範圍 `0x48960..0x52E1C`，大小 `0xA4BC`）做了
純離線的全零 byte 區間掃描，找到 82 段長度 ≥4 的候選，最大一段
`DS:0x427A`，長度達 25154 bytes（明顯是 BSS）。**但這個方法有已知盲點**：
磁碟上是零不代表執行期沒人寫入——交叉比對發現 `DS:0x165B`（長度 22 的零區間）
剛好涵蓋到已知一定會在執行期被寫入的 `name_table`（`DS:0x166D`，NAME-1 表
的動態遠指標，載入資源時才填值）。這證明**純靜態零區間掃描無法分辨「真正
沒人用的間隙」與「執行期才初始化的 BSS 變數」**，不能直接拿掃描結果當作
安全暫存格候選。

**下一步（已與使用者確認）**：等下一個對話重新連上 DOSBox-X-AI 的 MCP
bridge 後，用 Phase 7 新增的 memory watchpoint／`configure_dos_io_log`
等工具，對候選 DGROUP 區間做一整場遊戲執行期的動態監看，確認真的從未被
寫入，才能定案暫存格位置。**在此之前不要挑一個候選值就動手寫 patch。**

## 8. DOSBox-X-AI 現況（本輪意外發現，供下次接續）

- `D:\git\DOSBox-X-AI` 的 **Phase 7（A-E 全部五個 epic）已完工**，新增
  `configure_dos_io_log`／`list_dos_io_events`（DOS 檔案 I/O 事件記錄，含
  buffer 的 segment:offset:linear，可直接對應到 overlay manager 讀取
  `DSUN.EXE` 尾端 overlay pool 的每一次檔案讀取）、
  `configure_execution_trace`／`get_execution_trace`（中斷點命中前後最多
  4096 條指令的完整暫存器／反組譯 trace）、`get_mouse_capture`／
  `move_mouse_absolute`／`click_at`（real-mode 下的絕對座標點擊）。另外修掉
  一個 `-defaultdir` 選項解析導致 `-break-start` 不穩定的 bug。詳見
  `D:\git\DOSBox-X-AI\CHANGELOG.md` 與 `AGENT_GUIDE.zh-TW.md`。
- MCP server 已用 `claude mcp add dosbox-x-debugger -s local -- <venv python> <ai/server.py>`
  註冊在 `D:\git\Dark Sun Series` 這個專案的 local scope（`claude mcp list`
  確認為 `✔ Connected`），設定檔本身沒問題。但**同一個對話 session 重開
  VS Code／重連後仍抓不到新工具**——目前判斷是同一個對話的 deferred tools
  清單在對話一開始就固定了，換一個全新對話才會重新抓取 MCP 工具清單。下次
  要用這些工具，開新對話即可，不需要重新註冊 MCP server。

## 9. 目前狀態總結

- **不修改 v33／v26**：本輪全程只讀取 `DSUN.EXE`，沒有寫入、沒有建新版本。
- 已確定的、可直接沿用的結論：FBOV 格式解碼、v36 根因、DS-relative 差值公式
  （`CODE_BASE_runtime = DS − 0x14D0`，已交叉驗證）、呼叫端 14-byte 指令序列、
  解碼器返回序列的堆疊重排寫法。
- 唯一卡住的變數：DGROUP 暫存格的實際位置，需要下一輪連上 DOSBox-X-AI 用
  memory watchpoint 動態驗證後才能定案並實際建版測試。
