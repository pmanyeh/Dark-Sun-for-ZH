# v31 撤回 `%Fs` renderer 實驗修補

> 狀態更正：renderer 污染已撤回，但實機仍有大量中文 `?`。後續確認為 v18
> 稀疏 glyph bank 破壞固定槽位定位；請改用 v33。

> 日期：2026-08-17  
> 狀態：回退候選版已啟動，等待實機畫面確認

## v30 實機結果

三組畫面共同否決 v29/v30 的物件文字修補：

- 底部物件名稱可顯示「長劍」，右鍵資訊卡內容仍是亂碼；
- 原本正常的中文出現 `?`；
- 共用 UI 英文的字首亦遭破壞，例如 `STR`、`DEX` 等顯示為 `?TR`、`?EX`。

因此問題不是 GPL/NAME 翻譯封包或 DOSBox-X，而是實驗性的 `%Fs` far-call wrapper
錯誤介入共用 formatter/font renderer 路徑。v29/v30 均不可作為可玩基準。

## v31 回退內容

`patch_dsun_scratch_cache.py` 與 staging builder 現把該修補隔離為明確的
`--experimental-item-text-fix` 診斷選項，預設停用。v31 未啟用此選項，並保留：

- GPL2～6、GPLI-1、NAME-1 的累積中文封包；
- 六個 10×10 CJK bank；
- v26 已有的 EBOX 與 Base94 顯示修補；
- 從 v30 完整複製且經 SHA-256 比對的 `DARKRUN.GFF` 存檔。

```text
staging
scratch_test/cjk_display_staging_v31_renderer_rollback

patched DARKSUN.EXE SHA-256
0ce1554e2abc5f202e75eedf5f5df4ada6de33b3779b67f42a9e825779a4f2db

patched GPLDATA.GFF SHA-256
1a0bdf03f887a4cef65c2369ea2caaf075f997ffd34d8b858dd6fb824f6adea8
```

44 項 Python 測試通過。物件資訊卡亂碼仍列為未解決；後續須重新確認 `%Fs` 的
字串指標、位元組消耗規則與 font renderer 呼叫契約，不再沿用 v29 wrapper。
