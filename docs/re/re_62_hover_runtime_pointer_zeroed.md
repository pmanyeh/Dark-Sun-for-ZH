# hover 閃退根因：DGROUP pointer offset 在 runtime 被清零

> 日期：2026-09-09

## 動態證據

對 `0x06E288` hover consumer 製作磁碟 `EB FE` 診斷版後，實機凍結於：

```text
CS:IP = 5C09:2508
DS = SS = 4B7A
AX = 0011
[DS:6100] = 0000:0000
[DS:A378] = 80E3:0004
[DS:166D] = 78E7:0004
```

這同時證明：

- overlay 的真實 logical address 會隨載入改變，但 local IP `2508` 穩定；
- consumer 執行時 DS 確實是 DGROUP；
- `DS-0x14D0 = 36AA` 公式正確；
- 真正的閃退原因是 pointer cell 的 offset word 為零，而非 segment 計算；
- builder 寫在 MZ 磁碟映像中的 `5414:0000` 會在 startup／Load 初始化時被清零。

因此原 redirect 實際執行：

```text
mov [6102],36AA
call far [6100]       ; 實際變成 call 36AA:0000
```

## v41 修正

利用 `51F1` 可容納 17 bytes 的已驗證小區，安裝：

```text
mov word [6100],5414  ; 6 bytes
<原 v33 字高 helper> ; 11 bytes，語義 byte-identical
```

再將原 `53D6` helper 等長 redirect 到 `51F1`。這會在正常 glyph height 查詢時
反覆恢復 pointer offset，而且完全保留 v33 只有 `0x7F` 使用 10 rows 的既有語義；
不會重現 v39 把 `0x01..0x07` 全域改成 10-row 所造成的 Load Game 崩潰。
