# Base-94 演算法 resolver 實機驗證

> 日期：2026-08-14  
> 前置文件：`re_23_printable_triple_transport_runtime_proof.md`

## 1. 結論

DSUN renderer patch 已不再以 EXE table 列出每個 CJK triple。130-byte resolver 直接
計算完整 CJK ID，12 組低／高／跨 bank 邊界皆通過動態驗證，畫面完整顯示：

```text
中文顯示成功中文顯示成功
```

第 12 字依 16-pixel advance 正確換到第二行，後方英文正常接續。這證明三個 transport
bytes 在 ID decode、width/layout 與 glyph rendering 中只代表一個 glyph。

## 2. 演算法

```text
if byte0 != '^':
    return ordinary byte

d1 = byte1 - '!'
d2 = byte2 - '!'
require 0 <= d1,d2 <= 93

id = d1 * 94 + d2
```

合法 digit 全為 GPL 7-bit packed string 可往返的 printable bytes。EXE 中原先
12-entry、60-byte proof table 在本版保持全零；resolver 不依賴逐字資料。

## 3. 動態 ID 證據

在公式完成後的 `36AA:5451` 設斷點，取得：

| ID | Runtime bytes |
|---:|---|
| 0 | `5E 21 21` (`^!!`) |
| 93 | `5E 21 7E` (`^!~`) |
| 94 | `5E 22 21` (`^"!`) |
| 187 | `5E 22 7E` (`^"~`) |
| 4418 | `5E 50 21` (`^P!`) |
| 4511 | `5E 50 7E` (`^P~`) |
| 8742 | `5E 7E 21` (`^~!`) |
| 8835 | `5E 7E 7E` (`^~~`) |
| 255 | `5E 23 64` (`^#d`) |
| 256 | `5E 23 65` (`^#e`) |
| 880 | `5E 2A 43` (`^*C`) |
| 881 | `5E 2A 44` (`^*D`) |

第一輪 engine traversal 在最後一字前重新開始；第二輪完整命中 0～881。這說明先前
暫時未觀察到 881 是 traversal 順序，不是漏字。最終畫面亦直接確認 880／881 正常。

## 4. `^^^`／ID 5795 負面邊界

曾嘗試把 `^^^` 作 literal caret escape。resolver 正確計算 ID 5795 並消耗三 bytes，
但 legacy `0x5E` glyph 本來就是向下的 `v` 形，而非可見 caret。

再把 `^^^` 分配成中文字後，該字本身能顯示，但後續位於換行點的 `^*C` 被拆成三個
legacy glyph（`v`、測試槽「功」、`c`）。移除 `^^^` 後，相同演算法與相同 880／881
立即恢復正常。因此正式規格為：

```text
literal '^'        forbidden by importer
triple '^^^'       reserved / never emitted
CJK ID 5795        reserved / never assigned
usable capacity    8,835 IDs
```

Runtime 若遇到保留碼會消耗完整 triple 並回傳單一 `?` replacement，避免 pointer
錯位；正式輸入端則在封裝前直接拒絕它。

## 5. 最終測試檔

```text
DSUN.EXE SHA-256 692d181925a592a0ea80e2f3e7847fd662151a788d48bf388b275b21ad014df7
resolver size      130 bytes
lookup table       unused / zero-filled
```

## 6. 下一步

Transport 與 ID decoder 已可擴展到完整 mapping。下一階段是：

1. 把 UTF-8 translation importer 接到 `localization/cjk_mapping.json`。
2. 測試 `%` 格式參數、TAB、換行、MORE 與長句。
3. 實作跨 segment 的 far-bank loader 或單 glyph scratch cache，載入正式 881 字字庫。
