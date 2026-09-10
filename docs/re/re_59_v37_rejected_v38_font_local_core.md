# v37 全黑根因隔離與 v38 FONT-local core

> 日期：2026-09-09

## 1. v37 實機否決

v37 啟動後為全黑畫面。guest framebuffer 在約 6.7 秒時只有單一黑色，穩定 v33
控制組在相同時間則正常顯示 SSI 標誌，因此不是視窗擷取或等待時間問題。

逐層還原結果：

- pointer cell `DS:6100` 恢復全零：仍全黑；
- 四個 overlay consumer 與 pointer cell 全部還原，只留 resident core 與字高
  redirect：仍全黑；
- 再還原字高 redirect，只在 `51F1..537F` 留下 core：仍全黑；
- `51F1` 單一 byte、core `0..100`、core `200..399`：均可正常啟動；
- core `0..200` 或 `100..150` 的完整片段：全黑。

結論：`36AA:51F1..53A1` 不是可靠 resident code cave。磁碟上的連續零值與沒有
MZ relocation，只能證明靜態形狀，不能證明啟動期不會載入、執行或作為工作區使用。
`re_54` 與 `re_57` 對這段 433-byte cave 的安全判定正式撤回。v36 的 relocation
錯誤仍然成立，但不是這條設計唯一的啟動失敗來源。

## 2. 經 framebuffer 驗證的兩個小型 resident 區

以下組合在 v33 控制組上可正常顯示 SSI 開場：

- `51F1..5201`：17-byte 擴充字高 helper；
- `53D6..53E0`：跳往上述 helper 的等長 near redirect。

`5414..541F` 的 12 bytes 則是先前 item formatter 實驗已使用且能正常啟動的
既有空位。v38 將其作為唯一 resident trampoline，不再把大型 core 放入 EXE 零區。

## 3. v38 設計

FONT-100 配置改為：

```text
0x206B              legacy staging record
0x20D1..0x239A      seven persistent 10x10 slots
0x239B..            self-contained NAME decoder/cache/CJB1 loader
```

四個 overlay consumer 仍以 14-byte DS-relative 序列呼叫 `DS:6100`。pointer cell
的固定 offset 改為 resident trampoline `0x5414`；trampoline 讀取 `DS:A378` 的
FONT far pointer，加上 `0x239B` 後以 `retf` 轉入 FONT-local core。大型 core 因而
位於已由 GFF chunk 長度正式配置的 FONT 記憶體，不再依賴偽 code cave。

FONT-local core 為 633 bytes，內建 C0 到 C5 的 open/read/close loader，因為原本
resident loader 使用 near `ret`，不能直接跨 segment 呼叫。核心和七個 persistent
slots 合併後 FONT-100 為 9748 bytes，仍遠低於 16-bit offset 上限。

## 4. 驗證狀態

離線測試與 GFF 回讀驗證通過。新 staging：

```text
scratch_test/cjk_display_staging_v38_font_core
```

v38 guest framebuffer 在約 6.6 秒正常顯示 SSI 標誌，已通過 v37 未能通過的啟動
煙霧測試。仍需人工進入物品欄，驗證底部 hover、右鍵說明卡及右側裝備欄四個
consumer 的實際呼叫 ABI、中文字形載入與堆疊平衡；通過前仍是 candidate。
