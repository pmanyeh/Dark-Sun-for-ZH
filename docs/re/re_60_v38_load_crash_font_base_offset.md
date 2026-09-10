# v38 讀檔閃退：FONT runtime base offset 修正

> 日期：2026-09-09

v38 可正常顯示開場與主畫面，但讀取與 v33 byte-identical 的 `SAVE01.SAV` 時閃退。
這將失敗點縮到載入完成後第一次使用 NAME consumer 的路徑。

既有動態紀錄 `re_15` 與 `re_18` 都顯示：

```text
[DS:A378] = FONT segment:0004
```

v38 的 trampoline 正確以 `[A378].offset + 0x239B` 進入附加 payload，但核心卻以
`0x239B` 作為 link address。由於 FONT payload 的 runtime base offset 是 `0x0004`，
核心中所有 `CS:` absolute labels 與實際配置相差 4 bytes；第一次存取 cache state、
bank filename 或 name buffer 就會讀寫錯誤位置。

修正後明確拆成：

```text
FONT payload core offset = 0x239B
FONT runtime base offset = 0x0004
core link address        = 0x239F
```

resident trampoline 仍將 `0x239B` 加到 `[A378]` 的既有 offset，因此入口實體位置
不變；只有組譯時的 absolute label 基準修正為真正 runtime IP。下一個隔離 build
版本為 v39，仍需重新驗證讀檔與三個物品名稱畫面。
