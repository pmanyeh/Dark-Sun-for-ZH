# v26 GPLI 事件重定位與正式可玩 checkpoint

> 日期：2026-08-16  
> 前置：`re_44_gpl_external_entry_abi_and_prisoner_talk.md`

## 正式 checkpoint

```text
scratch_test/cjk_display_staging_v26_gpli_event_relocation_gap2
```

v26 已取代 v15，成為目前的正式可玩 checkpoint。

本版保留 v15 的 10×10 CJK 顯示、9-row UI 與 EBOX 行距設定，並納入兩個已驗證的
GPL 位址相容性修復：

- GPL-3 的外部入口位址（出口 Yes/No 觸發）。
- `GPLI-1` 事件表的 GPL-5 位址重定位（鬥獸場受綁囚犯的 Talk 觸發）。

## 建置識別

```text
patched DARKSUN.EXE SHA-256
a4b6c99a281a7b4c34412287fd111938bdef2298362e402bb72ba2b6e60148f6

patched RESOURCE.GFF SHA-256
4a8fe1be2a4161622545d39c50d54d3312a4e60afed44aa49c621f349601c726

patched GPLDATA.GFF SHA-256
0065d7de6499fd0f538284fd3787f71d8bf126660e3b054164b89a87ae11365d
```

其 `build-manifest.json` 的關鍵設定如下：

- `ebox_layout_line_gap = 2`
- `ebox_next_page_delta = -3`
- GPLDATA 的變更僅限 GPL-2～GPL-5 與 GPLI-1；其餘 1078 個非目標 chunk 維持不變。

## 已完成的實機回歸

於 v26 的鬥獸場流程已逐項確認：

- 受綁囚犯的 Talk 對話可以觸發。
- 出口的 Yes/No 對話可以觸發。
- 選擇 Yes 後可正常轉場。
- 競技場戰鬥可正常觸發。
- 中文對話的行距已恢復為 v15 的可讀布局。

因此，v26 同時覆蓋了導致 v20/v23/v24/v25 不能升格的兩個功能缺口與 v25 的行距回歸。

## 後續原則

未來的試驗版應由 v26 複製或以其 manifest 重建；不要再以 v15、v20、v23～v25 作為
新功能的可玩基準。若後續測試發現新的功能缺口，應另建新 staging 版本，保留 v26 作為
可回退的正式 checkpoint。
