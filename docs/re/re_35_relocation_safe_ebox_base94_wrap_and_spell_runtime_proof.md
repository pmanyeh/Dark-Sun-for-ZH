# Relocation-safe EBOX Base94 換行與法術說明執行期證明

> 日期：2026-08-15  
> 前置：`re_33_global_font_height_text_loss_and_9row_recovery.md`  
> 測試 build：`scratch_test/cjk_display_staging_9row_v5`

## 1. 結論

9-row v5 已在遊戲的法術說明視窗完成兩筆不同文本的執行期驗證：

- `BLESS` 不再於行首顯示 `""`、`!z` 等 Base94 尾碼。
- `ENTANGLE` 也能正常換行，未出現傳輸碼外漏或閃退。
- 畫面文字與翻譯來源逐字相同；差異只剩 EBOX 依可用寬度產生的換行。

這證明 EBOX 現在把 `^xy` 視為一個寬 10 pixels、長 3 bytes 的顯示 token，
而不是三個彼此獨立的 ASCII bytes。

## 2. 問題的精確成因

舊版 EBOX layout loop 位於 `341D:04A6`，每次只執行 `inc si`。
因此 line wrapper 可能在 `^xy` 中間切斷：

```text
加 = ^""   -> 上一行留下 ^，下一行外漏 ""
前 = ^!z   -> 上一行留下 ^，下一行外漏 !z
```

BLESS v3 的實際切行資料正好重現這兩種錯誤，所以問題不在字型 bank、Unicode
mapping 或翻譯文本，而在 EBOX 的 byte-wise width/layout 邏輯。

## 3. v5 relocation-safe 修正

v5 保留原本含 MZ relocation 的 far stack-check prologue，只修改三段不含 relocation
word 的範圍：

```text
341D:0214..0239  width body：'^' 回傳寬度 10
341D:0265..0296  compact locals + token advance helper
341D:04A6..04A9  呼叫 helper，再沿用原本的 jnc
```

helper 在目前 byte 為 `^` 時令 `SI += 3`，否則 `SI += 1`，最後重建原 loop
需要的 `cmp si,[bp-0C]` flags。

patcher 也會解析 DSUN.EXE 的 MZ relocation table；任何 patch 若碰到 relocation word
的任一 byte，build 會直接失敗。v5 三段 patch 的 relocation overlap 均為 0，鄰近的
原始 relocation 仍保留在 raw file offsets `0x315A2`、`0x315D6`、`0x315F3`。

## 4. 失敗方案與排除理由

- 將 helper 放在 `341D:8888`：real-mode physical address 會 alias 到其他 segment 的
  有效資料，法術 UI 執行後閃退，因此棄用。
- v4 原地改寫較大的 EBOX 區段：覆蓋了 MZ relocation words；DOS loader 載入時又修改
  新指令 bytes，造成文字全空白，因此棄用。
- cache 延伸到 `36AA:5557`：法術 UI 會覆寫 `36AA:5534` 以後的區域。現行 cache
  固定為 218 bytes、`36AA:545A..5533`，並採每 glyph open/read/close。

## 5. BLESS 逐字比對

翻譯來源：

```text
祝福術：使友方角色的 THAC0 提升 1 點。效果不可疊加。適合在戰鬥前施放。
```

畫面重組後：

```text
祝福術：使友方角色的
THAC0 提升 1
點。效果不可疊加。適合在戰
鬥前施放。
```

將畫面換行移除後與來源完全相同。舊版出現於「加」與「前」附近的 `""`、`!z`
均已消失。

## 6. ENTANGLE 逐字比對

翻譯來源：

```text
纏繞術：使大片植物突然生長纏繞。豁免失敗的受害者移動會變得非常緩慢。
```

畫面依 EBOX 寬度分行，但文字順序與內容完整，沒有 `^`、Base94 尾碼或未知符號外漏。
第二筆法術也正常顯示，排除了只對 BLESS 特例成立的可能。

## 7. 可重現 build 身分

```text
patched DSUN.EXE SHA-256
d602eb1acf5b9df8fbc643ce23355d585d3450ba6b5f7d39c8b228cd83b1fd4a

patched RESOURCE.GFF SHA-256
32a5a88235850690ceb662e67262edc1138926d95aeea0763049ae35558c10c7

RESOURCE target chunks       173
RESOURCE unchanged chunks   1031
scratch cache bytes           218
```

啟動仍必須使用原始三份 conf 與 `DARKSUN.BAT`，cycles 固定為 7000；不直接執行
`DSUN.EXE`。

## 8. 目前邊界

本次證明完成的是 SPIN 法術說明的傳輸、glyph 載入與 token-aware 換行。Fusion Pixel
10x9 仍是流程驗證用的暫用字型；未來可替換為更合適的小字型。15-row 路線也保留為
後續研究方向，但需要另行解決全域 FONT line-height 與 paginator 的互動，不能直接替換
目前的 9-row 可玩基準。
