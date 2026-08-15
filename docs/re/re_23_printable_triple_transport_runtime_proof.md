# Printable-triple transport 實機驗證

> 日期：2026-08-14  
> 前置文件：`re_22_formal_unicode_cjk_mapping_and_bank_pipeline.md`

## 1. 結論

第一版 control-byte 雙位元組 transport 已由實機否決；替代的三 byte printable
transport 已通過 GPL 往返、12 組動態邊界匹配與完整畫面驗證：

```text
CJK glyph = '^' + digit1 + digit2
digit      = 0x21..0x7E ('!'..'~')
CJK ID     = (digit1 - 0x21) * 94 + (digit2 - 0x21)
```

畫面實際完整顯示：

```text
中文顯示成功中文顯示成功
```

## 2. Control-byte pair 的負面證據

失敗版使用 control leads `01、02、0B、12、7F`。磁碟端 GPL assembler、GFF
replacement 與重新抽取均逐 byte 一致，但實機只顯示「顯 &」：

- 「顯」來自未被取走的 trail `$`；測試 legacy `$` glyph 正是「顯」。
- `&` 是另一筆未被取走的普通 ASCII trail。
- 設於 resolver found branch 的斷點完全沒有命中。

因此 control leads 在 renderer resolver 前已被上游控制碼流程消耗。失敗與 FONT
bank、CJK ID lookup 或 glyph rasterizer 無關；正式 transport 不可使用 control bytes。

## 3. Prefix 選擇

掃描 `dialogue_units.csv` 與 `localization_manifest.csv` 的全部原文：

```text
'^' occurrences = 0
'~' occurrences = 1
```

因此選 `^` 作固定 prefix。兩個 base-94 digits 提供 8,836 combinations。後續 re_24
證明 `^^^` 不適合作 literal escape 或中文字：它本身可解析，但會使後續行邊界 traversal
拆分下一組 triple。因此 `^^^`／ID 5795 永久保留禁用，literal `^` 由 importer 拒絕；
可用容量為 8,835 glyph IDs，足以涵蓋目前 881 字及完整遊戲後續翻譯。

## 4. 12 組邊界

| CJK ID | Triple |
|---:|---|
| 0 | `^!!` |
| 93 | `^!~` |
| 94 | `^"!` |
| 187 | `^"~` |
| 255 | `^#d` |
| 256 | `^#e` |
| 880 | `^*C` |
| 881 | `^*D` |
| 4418 | `^P!` |
| 4511 | `^P~` |
| 8742 | `^~!` |
| 8835 | `^~~` |

測試字串 decoded length 仍為 58 bytes；GPL-2 chunk 仍為 9,792 bytes。

## 5. 靜態往返

```text
GPL-2 SHA-256  70a0cc9808eec75aa2372edda017c30fa803db1fbe62ed05d5af3c8e52ea7890
FONT SHA-256   7babcb9c95dea76d2694d87aca1883694e6234fde55d93d1966328577ba18e2d
DSUN SHA-256   8f4696814fc0097e05957e1660881fde0c4968dde55e2c45cb224cace7510f01
```

GPL/FONT replacement 後重新抽取與輸入逐 byte 相同；disassembler 亦重新取得完全相同
的 36 transport bytes。

## 6. 動態證據

在 triple resolver found branch `36AA:5447` 停住，第一筆 live state：

```text
ES:BX  = 4B7A:FCE6
bytes  = 5E 21 21 (^!!)
SI     = 54D0
CJK ID = 0
```

自動繼續並記錄後續 layout／glyph 活動，12 組 triples 全數匹配，包含跨 255、
目前 registry 尾端 880／881，以及 ID space 上界 8835。
解除斷點後，使用者確認 12 個中文字完整、順序正確。

## 7. 下一步

本次 resolver 仍以 12-entry exact table 提供嚴格 proof。下一版將改為：

1. 直接計算 `(digit1-0x21)*94 + (digit2-0x21)`。
2. 保留 `^^^`／ID 5795，輸入端不得分配或產生。
3. 對無效 triple 保留普通 ASCII，不越界讀取。
4. 再接正式 881-entry mapping 與 far-bank glyph storage。
