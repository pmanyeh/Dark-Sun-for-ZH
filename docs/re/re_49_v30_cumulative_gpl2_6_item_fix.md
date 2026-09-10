# v30 累積中文封包與物件說明修正

> 狀態更正：實機否決。`%Fs` 實驗修補未解決物件資訊卡，並污染共用文字路徑，
> 造成正常中文與英數字首出現 `?`。v30 已由撤回該修補的 v31 取代。

> 日期：2026-08-17  
> 狀態：已完成自動測試並啟動實機候選版；等待畫面確認

## 問題與原因

v29 建置時直接使用 `scratch_test/gpl6_balkazar_zh_v1`。該封包是由英文原版建立、
只含本輪 GPL6 相關的 45 筆修改，不是可獨立遊玩的累積封包，因此先前 GPL2～5、
GPLI-1 與 NAME-1 中文全部退回英文。這不是 DOSBox-X 更新造成的顯示問題。

## 修正

`compile_gpl_dialogue_patch.py` 新增 `--prior-package`，可在保留原始 GPLDATA 指紋與
全容器驗證的前提下，把新對話批次疊加到既有中文封包。它同時：

- 驗證 prior package 的原始檔與 patched payload 指紋；
- 保留既有 chunk、edit、NAME metadata 與 unit ID；
- 拒絕直接疊加已修改過的對話 chunk，避免以舊位址套用到已重排資料；
- 以 Steam 原始 GPLDATA 為 baseline，重新驗證所有非目標 chunk 未變。

本輪以 `gpl5_gpli_name_v2` 為 prior package，再加入 GPL6 批次，產生：

```text
scratch_test/gpl6_cumulative_name_v2
scratch_test/cjk_display_staging_v30_cumulative_item_fix
```

累積封包包含 10 個目標 chunk、286 個對話 unit、618 筆修改：

```text
GPL-2, GPL-3, GPL-4, GPL-5, GPL-6, GPL-9, GPL-162, GPL-195,
GPLI-1, NAME-1
```

其中 NAME-1 保有 321 筆中文物件名稱；v29 的 `%Fs` 物件說明 far-call 修正也保留在
同一份 v30 執行檔中。

## 建置識別

```text
patched DARKSUN.EXE SHA-256
25c8710e4a484b8d26e581f1e0f4a0f30f9c5acab8813049d6cc9a6c3bfd3673

patched RESOURCE.GFF SHA-256
4a8fe1be2a4161622545d39c50d54d3312a4e60afed44aa49c621f349601c726

patched GPLDATA.GFF SHA-256
1a0bdf03f887a4cef65c2369ea2caaf075f997ffd34d8b858dd6fb824f6adea8
```

完整 Python 測試共 44 項通過。v30 已以 DOSBox-X-AI 啟動，下一步先確認一般中文
文本已恢復，再對長劍按右鍵驗證物件說明不再亂碼。
