# 跨 255 CJK ID 與多 bank 實機驗證

> 日期：2026-08-14  
> 前置文件：`re_20_independent_cjk_id_table_six_glyph_proof.md`

## 1. 結論

Dark Sun 中文 renderer 相容層已成功使用超過 8-bit 範圍的 CJK IDs，並跨兩個
CJK2 banks 選取字模：

```text
中 文 顯 -> IDs   0,   1,   2 -> bank 0
示 成 功 -> IDs 256, 257, 258 -> bank 1
```

實機畫面完整顯示「中文顯示成功」，使用者確認後三字「示成功」亦正常。這證明
CJK glyph identity、offset lookup 與 bank selection 已不受原 FONT-100 的
256-slot 上限限制。

## 2. 測試 pair 與 16-bit IDs

為保持 GPL packed string 的 7-bit 可往返性，本次使用六組明確的 printable pairs：

| Pair | CJK ID | Bank | Index |
|---|---:|---:|---:|
| `{!` | 0 | 0 | 0 |
| `{$` | 1 | 0 | 1 |
| `{&` | 2 | 0 | 2 |
| `}e` | 256 | 1 | 0 |
| `}f` | 257 | 1 | 1 |
| `}g` | 258 | 1 | 2 |

GPL-2 測試字串仍維持 58 bytes，重新組譯後 chunk 仍為 9,792 bytes：

```text
{!{${&}e}f}g  CJK 16X15 TEST..............................
```

重新封裝後抽取結果與 assembler 輸出完全一致：

```text
SHA-256 e1303f9d0f4bcd6d3d8e94e57dc9f9e6ec311d26f87435577e1d90f592a2c0cf
```

## 3. CJK2 extension

`tools/build_font100_cjk_probe.py` 現建立兩個 bank：

```text
CJK2 header
  magic            "CJK2"
  version          2
  bank_count       2
  glyph_height     15
  bank_capacity    256
  directory_offset 16

u16 bank_offsets[2]

bank:
  u16 glyph_count
  u16 table_offset
  u16 record_offsets[glyph_count]
  glyph records...
```

每個 record offset 相對於自己的 bank；bank offset 相對於 CJK2 extension。所有
offset 保持 u16，確保單一 bank 不跨越 64KB；16-bit ID 的高 byte 選 bank，低
byte 選 bank 內 glyph。

本次尺寸與雜湊：

```text
legacy FONT payload  13,888 bytes
CJK2 extension        1,492 bytes
total                15,380 bytes
SHA-256 18a5dee201c3b80ff2c68179c1c5bb6e86236014fbf30146eaa709b87feb1976
```

重封裝後重新抽取，SHA-256 完全相同；legacy offset table 保持不變。

## 4. Resolver

共同 resolver 位於 `36AA:5420`，大小 111 bytes。它先在 code-segment pair table
中取得完整 u16 ID，再執行：

```text
bank  = ID >> 8
index = ID & 0xFF

bank_offset   = CJK2.bank_offsets[bank]
record_offset = bank.record_offsets[index]
payload_offset = 0x3640 + bank_offset + record_offset
```

最後把 `payload_offset` 寫入唯一的 runtime marker entry `glyph_offsets[0x7F]`，
並回傳 `0x7F` 給原 width／glyph lookup。marker 只是一個每字更新的相容
trampoline，不承載 CJK identity。

測試版 DSUN.EXE：

```text
SHA-256 ce0e7f73b7003ddd06f53d0a7704e3d1a118b5cf693c7e1237eee477bc156997
```

## 5. 動態證據

在 resolver 寫 marker 前的 `36AA:5481` 與原 glyph width read `36AA:06FE`
設斷點，取得：

| CJK ID | Bank offset | Payload record | Runtime record | Width |
|---:|---:|---:|---|---:|
| 0 | `0x0014` | `0x365E` | `80E3:3662` | 16 |
| 1 | `0x0014` | `0x3750` | `80E3:3754` | 16 |
| 2 | `0x0014` | `0x3842` | `80E3:3846` | 16 |
| 256 | `0x02F4` | `0x393E` | `80E3:3942` | 16 |
| 257 | `0x02F4` | `0x3A30` | `80E3:3A34` | 16 |
| 258 | `0x02F4` | `0x3B22` | `80E3:3B26` | 16 |

width/layout pass 與實際 glyph pass 都依序解析出同一組 IDs。後三筆的 `SI`
實際為 `0x0100、0x0101、0x0102`，且 bank offset 從 `0x0014` 切換為
`0x02F4`，完成跨 255 與跨 bank 的直接動態證明。

## 6. 已完成的容量突破

至此已依序證明：

1. 兩 bytes 可只消耗並繪製一個 glyph。
2. 多組 DBCS 可連續顯示、混排、分頁與回畫。
3. FONT chunk 尾端可承載 appended CJK data。
4. 原 renderer 可畫 legacy payload 之外的 records。
5. 獨立 CJK offset table 可選擇多筆 records。
6. u16 CJK ID 可跨越 255 並選擇不同 banks。

## 7. 下一步：正式字庫管線

renderer 容量模型已打通。下一階段應由逆向原型轉為資料管線：

1. 從繁體中文翻譯稿統計 unique characters。
2. 固定 pair 編碼空間與 `%`／NUL／ASCII escape 規則。
3. 將 Unicode 字元穩定分配為 u16 CJK IDs。
4. 依每 bank 的實際 byte 大小切分 glyph records，而非只按 256 筆硬切。
5. 產生 CJK2 directory、banks、mapping manifest 與 patched FONT payload。
6. 讓 GPL reassembler／文字導入器自動把 UTF-8 翻譯轉成遊戲 pair bytes。
7. 用長句、精確行尾、MORE、格式參數與完整劇情流程做回歸測試。

