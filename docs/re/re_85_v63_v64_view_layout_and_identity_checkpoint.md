# v63/v64：能力值改版、裝備格回復、性別／種族中文化

日期：2026-09-17

## 1. 結論

兩個候選版皆已實機驗證：

- **v63**（`scratch_test/cjk_display_staging_v63_view_ability_regrid`）：能力值排版由
  「2 欄 3 列」改為「3 欄 2 列」（力量/敏捷/體質一排，智力/智慧/魅力一排）；同時把
  v58b／v59 移動過的 WIND-11500 裝備格與五個隱藏占位控制項，還原成 v57 的原始座標。
  這修正了 v58b 造成的迴歸——那三個真正裝備格與五個占位控制項同時被 USE 畫面等其他
  畫面共用同一套「查詢控制項座標」機制，移動它們會連帶影響 USE 畫面的技能／法術圖示
  排列。
- **v64**（`scratch_test/cjk_display_staging_v64_view_identity`）：VIEW CHARACTER 的
  性別（男性/女性）與種族（人類/矮人/精靈/半精靈/半巨人/半身人/穆爾人/螳螂人）已中文化。

兩版皆已用 GERAKIS、K'RATCHEK、CERMAK、CILLA 四位角色實機切換驗證，無當機、無重疊。

## 2. v63：能力值改版

`view_coordinates`（`cjk_name_slot_cache.asm`）改為：

```text
column = SI mod 3, row = SI div 3
x = 149 + 44 * column
y = view_y_origin + 12 * row
```

原本用 `mov ax,si; mov dx,149; cmp ax,3; ...` 這種 2 欄邏輯；新版改用「先算欄再算列」，
且改用堆疊暫存三欄計算所需的額外暫存值，因為 CX／BX 這兩個暫存器在呼叫端還有其他用途
（分別是 `view_label_decoded`／`view_number_entry` 最後要原封傳回的值），不能被
`view_coordinates` 覆寫。第一版曾誤用 CX 當暫存，造成堆疊回傳位址被破壞、實機測試 SP
不平衡；改成用堆疊 push/pop 暫存後修正。

裝備格佔用 Y=42~60，因此三欄二列的第一排必須從 Y=63 起（`VIEW_Y_ORIGIN=63`，v61 沿用
的 43 會與裝備格重疊）。`plan_name_slot_consumers.py` 的 `view_y_origin` 上限也從 52
放寬到 64（原上限是為 2 欄 3 列的高度算的，新版只需一次 12px 列距，可以更靠下）。

裝備格與五個隱藏占位控制項還原方式：直接拿 v57（`build_ability_ui_candidate.py` 的
輸出）裡從未被 v58b／v59 動過的 WIND-11500 整份覆蓋過去，不用手算「反向 patch」——
`revert_window()` 只驗證這 8 組座標確實回到 v57 的值，且其餘位元組沒有位移。

## 3. v64：性別／種族中文化

### 3.1 資料欄位（已用三個角色互相比對驗證）

VIEW CHARACTER 用的 71-byte 每角色身分紀錄裡：

| 欄位 | 位移 | 編碼 |
|---|---|---|
| 種族 | `record+0x18` | 1-indexed：1=人類...8=螳螂人 |
| 性別 | `record+0x19` | 1-indexed：1=男性，2=女性 |
| 等級陣列（多職業） | `record+0x24..0x26` | 每職業一個 byte，無則為 0 |

種族／性別字串**不是**預先組好的英文（跟材質那次不同），是單純數字欄位，繪圖函式
（檔案位移 `0x64B57`）當場用 `record+0x18`／`+0x19` 查一張常駐英文字串表。

### 3.2 繪圖機制與 patch 位置

繪圖函式先讀性別、算出對應英文字（`MALE`/`FEMALE`）在畫面上的寬度（呼叫一個量寬 helper），
以此決定接下來種族字要畫在哪個 X；然後讀種族、查表、呼叫全遊戲共用的
`%C%C%C%s` formatter（`339E:016D` 執行期位址）畫出來。

兩個 patch 點：

- **種族**（檔案位移 `0x64BB9`，22 bytes）：單一連續區塊、內部沒有 overlay relocation，
  直接整段換成 tag redirect。
- **性別**（檔案位移 `0x64B68`，49 bytes）：量寬 helper 呼叫的 segment word
  （`0x64B79`）是 overlay relocation 目標，不能覆寫。拆成三塊：
  - Zone A（14 bytes）：直接寫死一個中文寬度常數，再用短跳躍跳過中間；
  - Gap（13 bytes）：完全不動，內含上述 relocation word；
  - Zone C（22 bytes）：真正的 tag redirect。

FONT-local 解碼器新增 `fixed_identity`：`gender_label_entry`／`race_label_entry`
兩個外層 tag（`0xFFCD`／`0xFFCC`），對應內層 tag 範圍 `0xFFCE-0xFFCF`（性別，固定
2 字寬度，仿 `ability_text`）與 `0xFFD0-0xFFD7`（種族，2-3 字變動長度，仿材質的
offset table）。兩個 entry 都用 `les bx,[bp+0x0A]` 直接讀取呼叫端已經算好、還留在
`[bp+0x0A]` 的身分紀錄指標（BP 全程未被任何 redirect 動過），不需要額外傳參數。

### 3.3 新字形

種族清單裡 3 個字（穆、螳、螂，給 MUL／THRI-KREEN 用）在專案的 `localization/
cjk_mapping.json` 裡原本沒有。過程中另外發現：根目錄的 `cjk_mapping.json` 已經比
實際部署的 C0-C5 落後 3 個字（慧/捷/敏，v57 build 當時只更新了它自己那份
`cjk-mapping-v57.json` 複本，沒同步回根目錄）——因此本次改用同一套既有慣例：
以**上一版候選自己的** `cjk-mapping-v57.json`（已含 1317 筆）為基礎接著加、輸出
成自己的複本，完全不去動根目錄檔案，避免撞號。

新增字形用 `Fonts/Fusion_Pixel_10px.ttf`（10x10、pixel-aligned、threshold 64，
含陰影，不夾底）現刻——這組參數是從既有已部署 C0 bank 的 SHA-256 反查
`scratch_test/formal_cjk_fusion_10x10_v19_dense/cjk-bank-set.json` 對出來的，
確認 bank 0-4 逐 byte 相同後才套用；只有 bank 5（`C5`）改變，含新增的 40 筆
（37 舊 + 3 新）。

## 4. 尚未完成

- **陣營**（原假設呼叫點 `0x8A1DC`／內層 tag `0x2f`）：實機追出來的真正目的地
  （`5FB0:19A8`）看起來是另一段跟材質查詢類似但無關的邏輯，不是陣營繪製——
  舊有 `re_72` 文件對這個呼叫點的判定可能是錯的，需要重新調查。
- **職業／等級／經驗／HP／PSI**：完全尚未開始。等級陣列位移已確認
  （`record+0x24..0x26`），但職業本身的數字編碼還沒比對出規律。
- 使用者這次提供的排版示意圖（性別併入裝備格那一排、種族＋陣營合併一行、下半部
  職業/等級+經驗/HP+PSI/防禦+DAM 四行）尚未實作到位；v64 只是把既有兩行（性別+種族
  一行、陣營一行）原地翻譯，沒有搬動任何文字位置。

## 5. Hashes

```text
v63 DSUN.EXE（與 v61 相同，未修改）
3c56a1a724e1de0e0656a91c96a088cf6bd15b453e0f83a21315bd3d0653b879
v63 RESOURCE.GFF
00ea0d417135665facb8849bed57407b5a218b6aba2628e922d0d3d38ae60581

v64 DSUN.EXE
cf66f622557ca0f12e5e03c128c4e4e0c769217a7339103e4efc3cc94133a551
v64 RESOURCE.GFF
8a5ffd8a1d348abb3907d9035f1d4b6441228faa64804c8d2f03d4e0b812d297
v64 C5（新字形 bank）
5ef32f8c23e163909bbaa5c5ba2c9e02098c85a514eefbe1e668e271d0f8d641
```
