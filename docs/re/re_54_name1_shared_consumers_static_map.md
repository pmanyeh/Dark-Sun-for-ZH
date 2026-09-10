# NAME-1 三處亂碼與專用 consumer 靜態定位

## 1. 新的畫面證據

同一件物品（長劍）的 NAME-1 Base94 字串會同時出現在三處：

1. 右鍵物件說明卡；
2. 右側裝備／攻擊資訊；
3. 底部滑鼠懸停名稱。

三處顯示相同的亂碼，證明問題不是單一說明卡版面，也不能只修 `%Fs` 的
物件說明迴圈。三條 UI 路徑最後都直接使用 NAME-1 的固定 25-byte record。

## 2. NAME-1 基底指標

DSUN.EXE 的 DGROUP 內：

```text
[DS:166D] = NAME-1 table offset
[DS:166F] = NAME-1 table segment
record address = table base + name_id * 0x19
```

先前在執行期找到的 `7800:0E74`／實體 `0x78E74` 是整張 NAME-1 表的載入
位置，不是每次重繪另建的暫存字串。這也解釋了為什麼對該位置設寫入監看點
不會在切換面板時命中。

## 3. EXE 中已定位的 NAME-1 consumers

掃描 16-bit `imul reg, reg, 0x19`，排除一筆跨指令的誤判後，找到 8 個真正的
NAME-1 位址計算點，分布於 6 段常式：

| file offset | 後續行為 |
|---:|---|
| `0x059C27` | 將 NAME record 指標交給字串複製常式，先複製到 stack buffer |
| `0x06E288` | 以長度 `0x28` 將 NAME record 複製到 stack buffer |
| `0x072904` | 以 NAME 與物件附加欄位組成 stack buffer |
| `0x072955` | 把 NAME record far pointer 直接交給 `LCALL 0090:0A40` |
| `0x0817AC` | 把 NAME record far pointer 直接交給 `LCALL 0580:005C` |
| `0x08A925` | 把 NAME record far pointer 直接交給 `LCALL 0580:005C` |
| `0x08BECF` | 以 NAME 與物件附加欄位組成 stack buffer |
| `0x08BF00` | 以 NAME 組成 stack buffer，再交給 `LCALL 0090:0A40` |

其中 `0x072904/0x072955` 與 `0x08BECF/0x08BF00` 各是同一常式內「有附加
欄位／無附加欄位」的兩條分支。因此目前是 6 個獨立 consumer 常式，而不是
8 套完全不同的 renderer。

以上六段範圍已逐 byte 比對 v33 與乾淨英文 DSUN.EXE，結果全部相同。故這些
路徑不是 v33 patch 造成的退化，而是原版遊戲既有的 8-bit NAME 顯示架構。

## 4. 對修復設計的影響

不能再修改共用 `%Fs` 格式器來猜測物品卡行為；v34／v35 已證明該作法會造成
空白、閃退或 guest main-loop hang。新的候選應只作用於 NAME-1 consumer：

1. 先以精準 code breakpoint 判定畫面三處各命中哪一個 consumer；
2. 確認兩個下游繪圖入口使用的字型資源與 byte-to-glyph lookup；
3. 因 321 筆名稱共有 471 個不同中文字，不能用 128 個高位 byte 做永久全域映射；
4. 可評估依「目前物件名稱」動態載入最多 7 個暫存 glyph，並把該名稱轉成短
   8-bit 暫存字串；三個 consumer 若共享同一個當前物件，就能共同使用它；
5. 在完成離線 ABI、stack 與指標驗證前，不建立新的遊玩測試版，也不修改 v33。

## 5. 下一次執行期追蹤原則

- v33 保持 `autolock=false`，由使用者操作滑鼠；
- 一次只設 NAME-1 專用候選點，避免再對共用 glyph renderer 大範圍中斷；
- 先分別觸發底部名稱、右側資訊與右鍵說明卡，記錄實際命中的 consumer；
- 命中後只讀取 caller、NAME far pointer、字型／繪圖參數；不做 RAM hotpatch；
- 每次中斷都先通知使用者，完成採樣後立即恢復，不讓正常停住被誤認為閃退。

## 6. v33 執行期命中結果

### 6.1 overlay 位址不可由 EXE file offset 線性換算

最初把 file offset 加上 resident load bias 所得到的 breakpoint，會落到完全不同的
滑鼠判定程式。原因是這些 consumer 位於動態 overlay；每次切換畫面後，其實體載入
位置也可能改變。正確程序是：以每個 consumer 的獨特機器碼片段搜尋目前 640 KiB
guest RAM，確認 byte-for-byte 相同後，再從 signature 位置換算該次的 breakpoint。

### 6.2 底部 hover 名稱

游標移到長劍時，命中 `0x06E288` consumer 的當次執行位置 `5B7C:2508`：

```text
AX = SI = 0x001C             # NAME id 28 = Long Sword
[DS:166F:166D] = 78E7:0004  # NAME-1 table base
record = 78E7:02C0
bytes  = 5E 29 43 5E 21 7C 00  # 「長劍」Base94
```

此路徑先把名稱複製到 stack，組成：

```text
42 6F 6E 65 20 5E 29 43 5E 21 7C 00
Bone + 長劍 Base94
```

再經 `5B7C:2391 -> 4A96:005C thunk -> 5FC1:068D -> 5FC1:1ECF`，最後呼叫
`339E:016D` 格式器。實際格式為 `%C%C%C%s`；目標 `%s` 的直接返回位置是
`5B7C:1F4D`，其上一層 caller 是 `5B7C:073C`。

### 6.3 右側資訊與右鍵說明卡

在 `%s` case 入口 `339E:02D7` 以背景監看器自動略過非目標字串後，右側資訊的
長劍來源同樣是 `78E7:02C0`，直接返回位置為共用包裝器 `2143:0A6A`。

只看這一層仍無法區分右側資訊與說明卡。新增 saved-BP stack unwind 後，重新關閉／
開啟說明卡，得到首次建立順序：

| 顯示內容 | `%s` 上一層 caller |
|---|---|
| `Bone` | `6014:0F99` |
| `45$` | `6014:1194` |
| 長劍 `78E7:02C0` | `5B7C:2B9C` |
| `1D8-1` | `5B7C:2CD4` |

`5B7C:2B9C` 可精確對回靜態 `0x072955` 的 NAME 位址計算，以及
`0x072967 call 0090:0A40` 後的返回位址 `0x07296C`。因此右鍵說明卡的名稱專用
分支已正式定位。該包裝器執行期格式同樣確認為 `%C%C%C%s`，不是另一套未知
字型 renderer。

### 6.4 修復方向更新

三處亂碼並非三套完全分離的 glyph renderer；至少底部與說明卡最後都進入
`339E:016D` 的 `%s` case。v34／v35 直接替換全域 `%s` byte loop 造成空白、閃退或
hang，故不再採用。

下一個候選應在已定位的物品 caller／stack buffer 邊界處理：

- 說明卡：靜態 `0x072955` 分支（返回 `0x07296C`）；
- 底部 hover：組成 `Bone + NAME` 暫存字串後、進入共用 formatter 前的局部路徑；
- 右側資訊：以 `2143:0A40` 的上一層 caller 區分，不修改 `2143:0A40` 本身。

如此可以保留對話、法術與其他 `%s` 呼叫的既有中文顯示，不再承擔全域 formatter
ABI 退化風險。執行期追蹤全程未寫 guest RAM；結束後已移除所有 breakpoint、關閉
execution trace，並確認 guest 為 `running=true`。

## 7. 多格名稱快取候選（僅設計，尚未建版）

現行 v33 dense-bank scratch FONT 在 legacy payload `0x206B` 後只附加一筆
102-byte glyph record（10×10 + u16 width），
所有中文字共用 marker `0x7F`。這對低頻對話可工作，但物品畫面的持續重繪會讓不同
中文字互相逐字驅逐，並在每次 miss 執行完整 CJB1 DOS file I/O。

NAME 翻譯最長為 7 字，因此可評估：

1. 在 FONT-100 尾端附加 7 筆 102-byte scratch records（共 714 bytes）；
2. 使用 7 個不與 NUL／一般可印 ASCII 衝突的控制 byte 作為動態 glyph slots；
3. 維護 `CJK id -> slot` 小表，同一名稱重繪時直接回傳既有 slot，不再讀檔；
4. 在 `0x072955` 說明卡分支先把 NAME 複製／壓縮成局部 8-bit 暫存字串；
5. 底部 composite buffer 亦在 caller 邊界做相同轉換；
6. 先離線驗證 FONT offset table、payload 長度、slot 衝突、cache hit/miss 與所有
   stack/pointer 邊界，再考慮建立新版本。

七筆追加後 FONT payload 為 `0x206B + 7 * 102 = 0x2335`，仍在 16-bit offset
範圍內；但 runtime allocator 是否完整保留新長度、控制 byte 是否在物品 renderer
無特殊語義，仍需測試證據，現階段不能視為已證實可行。
# Seven-slot offline safety proof (2026-08-17)

The current v33 dense FONT payload is `0x206B` bytes.  A native 10-by-10 CJK
record is 102 bytes (`u16 width` plus 100 pixels).  The initial allocation proof
showed that seven contiguous persistent records fit the 16-bit FONT range; the
implementable layout below adds a separate staging record before those seven.

The proposed runtime glyph codes are `0x01..0x07`.  FONT-100's offset table
starts at `0x0108`, therefore their table entries are `0x010A..0x0116` in
two-byte steps.  These codes remain positive after the renderer's byte-to-word
sign extension and do not use NUL.  An offline scan found no occurrence of any
of these seven codes in:

- all 321 currently encoded `NAME_objects_translated.json` rows; or
- the active name portion (before NUL) of all 322 records in each of the four
  retained `scratch_test/gpl*_name_v*/NAME-1.bin` candidates.

`plan_dynamic_font_slots()` and its tests now prove each table entry resolves to
the exact appended record.  A full catalog pass also proves that the current
321 translated rows need at most seven total and seven distinct CJK glyphs per
name. `predecode_name_to_dynamic_slots()` preserves ASCII, replaces each Base94
triple with a one-byte slot code, and reuses a slot when a glyph repeats.

This is an allocation and transport proof only; it does not yet authorize a
runtime candidate.  Caller-local decoding and cache refresh semantics still
need to be designed and verified offline.

## Resident space and consumer redirect proof (2026-08-17)

The current single-glyph loader exactly fills resident range
`36AA:545A..5533`; there are zero spare bytes at its established runtime-safe
boundary.  The stable v33 executable does, however, retain 433 zero bytes at
`36AA:51F1..53A1`.  The corresponding file range has no MZ relocation words.
This is the candidate location for a reviewed name-level decoder and a loader
that accepts a destination slot.  It is not patched yet.

The three proven UI paths reduce to four static branches because the right-side
panel has two conditional forms.  At file offsets `0x06E288`, `0x072955`,
`0x08BECF`, and `0x08BF00`, v33 contains the same 14-byte sequence that turns
the NAME id already in AX into a far pointer and pushes segment then offset.
An equal-length plan can replace that sequence with a relocatable far call to
`2E86:51F1`, followed by pushes of returned `DX:AX`, without moving subsequent
instructions.  `plan_name_slot_consumers.py` verifies all four source
signatures, the exact replacement length, non-overlapping new relocation
words, and sufficient MZ-header relocation capacity.  It intentionally has no
function that writes an executable.

## Assembled name-cache core (offline only, 2026-08-17)

The first implementable layout needs eight appended 102-byte records, not
seven: the unchanged v33 loader continues to use `0x206B` as its staging
record, while persistent dynamic codes `0x01..0x07` point to `0x20D1..0x2335`.
The resulting FONT payload is `0x239B` bytes.  After each successful legacy
load, the core copies the 102-byte staging record into its persistent slot and
patches only that control code's FONT offset-table entry.

`cjk_name_slot_cache.asm` now assembles to 391 bytes at
`36AA:51F1..5377`, leaving 42 bytes before the verified `0x53A2` cave boundary.
It performs these operations without changing v33's legacy loader:

1. accept a NAME id in AX and return a resident far pointer in `DX:AX`;
2. reuse the prior decoded buffer when the NAME id has not changed;
3. parse printable Base94 triples, reuse repeated glyph IDs, and allocate no
   more than seven dynamic codes;
4. call the existing `0x545A` loader for a cache miss, then copy staging into
   the selected persistent FONT record;
5. preserve ASCII bytes and terminate the resident output buffer explicitly;
6. emit `?` and roll back a newly allocated slot if a glyph read fails.

The core also contains an extended glyph-height helper.  The in-memory patch
plan replaces v33's reviewed 11-byte helper at `36AA:53D6` with an equal-length
near jump.  Dynamic codes `0x01..0x07` and legacy marker `0x7F` therefore draw
all ten CJK rows, while ordinary characters retain the original nine-row
height.

This binary is assembled and size-checked by tests but is not injected into
v33.

## Isolated v36 candidate build (not runtime-validated)

After the in-memory executable and temporary full-build checks passed, the
reviewed plan was written only to:

```text
scratch_test/cjk_display_staging_v36_name_slots
```

Stable v33 was cloned rather than rebuilt from Steam sources.  Preflight proves:

- `SAVE01.SAV` is byte-identical to v33 and 66 other game files were preserved;
- `autolock=false`;
- DSUN.EXE SHA-256 is
  `38045f7f59e1f17df8f702053d64f283118658def9fe32ea9c9b122ee989a52f`;
- RESOURCE.GFF SHA-256 is
  `595f0ac7107640bfe96b30b6d1049c2421a0e446d2f3bd8574f580ed92814ec1`;
- only FONT-100 plus allowed GFF container metadata changed; all 1203
  non-target chunks are unchanged;
- FONT-100 is `0x239B` bytes and the name-cache core is 391 bytes.

### Runtime rejection

After v33 was closed normally, v36 was launched once.  DOSBox-X remained
`running=true` and emulated time advanced, but bridge framebuffer captures were
entirely black.  The candidate was closed and stable v33 was immediately
restored; a bridge capture verified the normal SSI opening screen.

Root cause: these four consumers are dynamically loaded overlays.  Their file
offsets cannot be registered in the main executable's MZ relocation table.
Doing so makes the DOS loader relocate unrelated startup memory.  Conversely,
omitting those relocation entries would leave the new direct far calls with an
incorrect runtime segment.  Therefore v36 and its direct far-call plan are
rejected.  Both executable-building entry points now fail closed.  The next
design must call through an overlay-safe indirect far pointer or reuse an
existing overlay relocation; the 391-byte decoder core and eight-record FONT
layout remain valid offline components.
