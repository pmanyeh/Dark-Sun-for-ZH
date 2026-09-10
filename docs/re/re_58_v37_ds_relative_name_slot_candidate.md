# v37 DS-relative NAME 多字形快取候選

> 日期：2026-09-09  
> 前置文件：`re_55_fbov_overlay_relocation_and_ds_relative_redirect_design.md`、
> `re_56_dgroup_tail_candidate_disproven_by_dynamic_watchpoint.md`、
> `re_57_session_handoff_scratch_cell_confirmed_next_is_v37_patch.md`

## 1. 本輪實作

v37 已把四個已確認的 NAME-1 consumer 改成 overlay-safe、無 relocation 的
DS-relative 間接 far call。四處檔案位移為：

```text
0x06E288
0x072955
0x08BECF
0x08BF00
```

每處原本的 14-byte `NAME_POINTER_SEQUENCE` 均以以下等長序列取代：

```text
8C DB                mov bx, ds
81 EB D0 14          sub bx, 0x14D0
89 1E 02 61          mov [0x6102], bx
FF 1E 00 61          call far [0x6100]
```

`DS:0x6100` 在磁碟映像中預先寫入 offset word `0x51F1`，segment word 留零；
每次呼叫前由 consumer 以 `DS-0x14D0` 更新 segment。這個設計沒有新增或修改
主 MZ relocation table，也不需要更動 overlay 私有 fixup。

解碼器返回序列同時改為在 `retf` 前重排 far-call 返回位址，將回傳的 `DX:AX`
指標留在原始 consumer 預期的堆疊位置。組譯後核心為 399 bytes，範圍仍完整落在
已驗證 resident cave `0x51F1..0x53A1` 內。

## 2. 離線驗證

新增兩項測試，驗證：

- 四處 redirect 恰為 14 bytes，且 byte sequence 完全符合設計；
- pointer cell 的檔案映射與初值正確；
- patch 前後主 MZ relocation 集合完全相同；
- resident core、height-helper redirect 與四個 consumer 均能回讀驗證；
- patch 不會修改 v33 來源檔。

完整測試結果：

```text
Ran 66 tests
OK
```

## 3. 建置結果

新 staging：

```text
scratch_test/cjk_display_staging_v37_name_slots
```

建置識別：

```text
DSUN.EXE SHA-256:
bdf603aceec2138db38f691ed3729ea0b31be0891c491907519cbb16f5aea515

RESOURCE.GFF SHA-256:
595f0ac7107640bfe96b30b6d1049c2421a0e446d2f3bd8574f580ed92814ec1

name-cache core: 399 bytes
FONT-100: 9115 bytes (0x239B)
main MZ relocations added: 0
```

RESOURCE.GFF 回讀驗證通過：FONT-100 是唯一目標 chunk，1203 個非目標 chunk
全部 byte-identical；另只允許容器索引 `GFFI-1.bin` 改變。v33 的其餘 66 個遊戲
檔案也全部保持不變，滑鼠設定為 `autolock=false`。

## 4. 執行期狀態與待驗證項目

v37 已成功啟動為獨立 DOSBox-X 行程，啟動八秒後仍正常回應，標題顯示
`DSUN - 7000 cycles/ms`。這是啟動煙霧測試，不等同於物品 renderer 驗證。

仍需由遊戲畫面逐項確認：

1. 底部物品滑鼠懸停名稱列（consumer `0x06E288`）；
2. 右鍵物件說明卡（consumer `0x072955`）；
3. 右側裝備／攻擊資訊欄的兩種條件分支（`0x08BECF`、`0x08BF00`）；
4. v33/v26 既有中文對話、SPIN、出口、轉場與戰鬥回歸。

在上述畫面通過前，v37 保持 candidate，不能升為正式 checkpoint。
