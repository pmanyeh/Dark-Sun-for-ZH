# 可變長 GPL 對話匯入器與 v7 checkpoint

> 日期：2026-08-15  
> 前置：`re_36_spin_title_description_hard_break_runtime_proof.md`  
> 狀態：靜態、容器與 Celgor 開場實機驗證全部完成

## 1. 本次目標

將 `dialogue_units.csv` 中四個 Celgor 開場單元經正式流程匯入 `GPLDATA.GFF`：

```text
DLG_f6c2fbaa84a9  今日法師賽爾戈將迎戰一頭兇猛的狂暴獸。
DLG_13ab12eaff4a  敬請觀賞！
DLG_6294a22b2cbb  別擔心，
DLG_67aa8858af43  。很快就輪到你了。退後觀看這場戰鬥吧。
```

第三、四筆之間原有的 `COMPLEX(... POV ... [19])` 動態姓名 print 指令保持不動，
因此遊戲仍會在「別擔心，」後插入當前角色姓名。

## 2. 安全匯入流程

`tools/compile_gpl_dialogue_patch.py` 執行：

1. 由 `unit_id` 對應 `dialogue_units.csv` 與 `dialogue_occurrences.json`；
2. 只接受 resolved、inline、compressed 的 GPL/MAS occurrence；
3. 用 append-only CJK mapping 轉為 runtime-proven Base94 triples；
4. 用 `gpl-disasm --json` 取得完整 IR，並以原 offset、opcode 與英文原文作三重 fingerprint；
5. 依 SSI 7-bit packed-string實際長度計算每筆 delta；
6. 重排全部 instruction offsets，重新定位 local branch opcodes；
7. 交給 `gpl-asm` validator 與 encoder；
8. 對 patched GFF 再反組譯，驗證 aligned、完整 consumed bytes 與四筆 payload；
9. 全抽取 1084 chunks，只允許 GPL-2 與容器索引 GFFI-8 改變。

匯入器不會修改原始 Steam 安裝，也不會依賴固定長度覆寫。

## 3. Branch relocation 證明

原始 GPL-2 能經 OpenDS round-trip 得到 byte-identical SHA-256。四筆中文 transport
的 packed length delta 分別是 `-1、-2、-2、-3`，因此 chunk 總長從 9792 bytes
變為 9784 bytes。

重定位後尾端相關 branch 包含：

```text
new 0x252B -> 0x25E7
new 0x25F0 -> 0x2635
```

`gpl-asm` validator 通過；patched disassembly 回報：

```text
bytes_consumed  9784
total_bytes     9784
aligned         true
```

若直接編輯含舊式 `label_0xNNNN` 的 listing 而未 relocation，validator 會拒絕指向
chunk 外的 branch。本匯入器使用 JSON IR 並顯式重定位，保留這項安全檢查。

## 4. GPLDATA 全容器驗證

```text
all chunks                    1084
target chunks                    1  (GPL-2)
changed target chunks            1
unchanged non-target chunks   1082
allowed metadata                 1  (GFFI-8)
```

```text
source GPLDATA.GFF SHA-256
405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04

patched GPLDATA.GFF SHA-256
9c31685a2538cdf10cb635965922c9b00ddf8500f434a5e4886aa02612ff7c47
```

## 5. v7 staging

```text
scratch_test/cjk_display_staging_9row_v7_celgor
```

v7 組合：

- v6 relocation-safe EXE 與法術名稱換行 RESOURCE；
- 更新後 901 個 active glyph 的 Fusion Pixel 10x9 CJB1 banks；
- 本次已驗證的 Celgor GPLDATA package；
- 與 v6 byte-identical 的 SAVE01.SAV 與 CHARSAVE.GFF。

自動測試共 23 項通過。

## 6. 實機結果

2026-08-15 使用者實機畫面確認：

```text
今日法師賽爾戈將迎戰一頭兇猛的狂暴獸。敬請觀賞！

別擔心，Gerakis。很快就輪到你了。退後觀看這場戰鬥吧。
```

EBOX 依寬度自動分為兩行加兩行；中文內容完整、順序正確，原 GPL 的兩個
`printnl` 保留段落，動態 `Gerakis` 正確出現在中文標點之間，也沒有 Base94 尾碼
外漏或後半段缺失。使用者評價為「堪稱完美」。

目前仍可見的版面限制是 10x9 glyph 與原生 line pitch 幾乎沒有垂直留白。這不影響
本次 GPL importer／pagination 證明；後續應優先研究 EBOX 的獨立 line-pitch，避免
藉由改動全域 FONT height 再度引入四行變兩行與 MORE 文本缺漏。

## 7. v8 line-gap A/B：拒絕

實驗版 `scratch_test/cjk_display_staging_9row_v8_linegap2` 只在重畫迴圈的 Y 推進增加
2 pixels，刻意不改 line table 與 paginator。實機結果是前幾行間距增加，但最後一行
超出 EBOX 既有 clip boundary，只剩字形頂部，看似亂碼。

因此「只改 draw Y、不同步 layout/clip」已由實機否決，不得取代 v7。測試後已立即
恢復 `cjk_display_staging_9row_v7_celgor`。後續若繼續改善，必須選擇下列之一：

1. 同步調整 line table、visible bounds 與 clip/pagination；或
2. 保持 9-row cell metric，在 glyph bitmap 內保留一列空白，先做不影響分頁的 A/B。
