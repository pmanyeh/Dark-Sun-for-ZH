# FONT-100 尾端 CJK bank 載入器實證

> 日期：2026-08-14  
> 前置文件：`re_17_six_pair_dbcs_pagination_proof.md`

## 1. 結論

Dark Sun 的 FONT resource loader 會按 GFF chunk 的完整長度配置與複製資料，並不會
在 legacy 256-glyph FONT payload 結尾截斷。將 258-byte `CJK1` extension 附加到
FONT-100 後，執行期可在 payload `+0x3640` 完整讀回，逐 byte 與磁碟資料相同。

這表示獨立 CJK offset table／pixel bank 可以直接承載於 FONT-100 chunk 尾端，
不必先新增另一種 GFF resource 或修改資源載入器。

## 2. Probe 結構

legacy FONT-100 長度為 13,888 bytes（`0x3640`）。測試工具
`tools/build_font100_cjk_probe.py` 在其後附加：

```text
CJK1 header:
  char magic[4]     = "CJK1"
  u16 version       = 1
  u16 glyph_count   = 1
  u16 glyph_height  = 15
  u16 reserved      = 0
  u32 record_offset = 16

record:
  u16 width         = 16
  u8 pixels[240]    = FONT-100 slot 0x40「中」的副本
```

尺寸：

```text
legacy payload   13,888 bytes
CJK1 extension      258 bytes
result payload   14,146 bytes
```

extension SHA-256：

```text
75db35d8abd4fae8cc0dd36b6157bf2f7b538d351332562568192eb5fe272932
```

完整 probe payload SHA-256：

```text
961bc166dac679a53ac1827d6e0a30a73e7021c12c88aaeb12a6e344a8e3e7c8
```

## 3. 磁碟與執行期驗證

`RESOURCE.GFF:FONT-100` 重封裝後重新抽取，與 probe builder 輸出 SHA-256 完全
一致。重啟遊戲並在 `36AA:0864` renderer 入口停止後：

```text
[4B7A:A378] = 80E3:0004
CJK1 magic  = runtime payload + 0x3640
```

比對結果：

```text
extension_equal = true
runtime extension SHA-256 = 75db35d8...
```

完整 payload 仍只有三個已知的 loader mutation：

```text
+0x006  00 -> 01
+0x01C  14 -> 11
+0x106  FE -> 2D
```

`CJK1` header、offset、width 與 240 pixel bytes 全部未被修改。

## 4. 意義與下一個測試（已由 re_19 完成）

此結果解除「資源載入器是否截斷 appended data」的不確定性。下一步不需改 loader，
可直接讓 renderer 指向 extension record：

1. 暫用 legacy slot `0xFF` 作為 DBCS marker。
2. 將 `glyph_offsets[0xFF]` 指到 payload 尾端的 CJK1 record。
3. 讓 `~A` 回傳 marker `0xFF`。
4. 在 `36AA:06FE` 驗證 glyph record pointer 落在原 payload 結尾之外。
5. 實機確認畫面仍顯示「中」。

這會是「第 257 筆字模資料確實被原 renderer 畫出」的最小證明；完成後再把單一
marker 擴展成真正的 16-bit CJK glyph id 與獨立 offset table。

實機結果見 `re_19_257th_appended_glyph_rendering_proof.md`：renderer 的 record
pointer 實際落在 `80E3:3654`，242-byte record 與磁碟資料完全一致，畫面第一個
「中」正常顯示。
