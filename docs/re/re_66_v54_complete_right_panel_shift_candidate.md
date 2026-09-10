# v54 右側資訊區整組上移 20px candidate

> 日期：2026-09-10
>
> 狀態：離線建置與差異稽核完成；尚待使用者實機驗證。

## 1. 設計變更

v53 只把武器區起點移到 `Y=109`，雖然最壞七列可避開底部控制區，卻壓縮了
AC 與第一列武器之間的空白。v54 改採使用者建議：以 v52 的相對配置為基準，
把整個右側資訊區上移 20px。

```text
區域                    v52 Y       v54 Y
能力標籤／底圖起點       53           33
六項能力數值起點         53           33
PSI/第一組資訊           99           79
PSI 數值                 99           79
AC/第二組資訊           113           93
武器區                  129          109
```

武器區仍使用已由 v52 實機確認的 10px 格線。最壞七列為：

```text
109, 119, 129, 139, 149, 159, 169
```

最後 10px glyph 使用 `Y=169..178`，完整位於約從 `Y=181` 開始的底部控制區
之前。各資訊子區塊間的相對距離則保持與 v52 相同。

## 2. File patches

```text
0x06F5A4  ability label/background Y       35 -> 21
0x06F5EB  six ability-value rows base Y    35 -> 21
0x06F61E  PSI/info label Y                 63 -> 4F
0x06F631  PSI/info value Y                 63 -> 4F
0x06F672  AC/second info row Y             71 -> 5D
0x06F6A9  weapon section Y (v52 value)     81 -> 6D
```

前五項皆為 `-20px`。最後一項在乾淨 v33 source 原本是 `0x78`；v52 曾改為
`0x81`，v54 的最終值為 `0x6D`，亦即相對 v52 上移 20px。

## 3. Build checkpoint

```text
scratch_test/cjk_display_staging_v54_shifted_item_panel

DSUN.EXE SHA-256
b4ac24402b28dd3be8388d628af86d6b0437b2c9a4a8aaf93142cfdf7c124cfa

RESOURCE.GFF SHA-256
d42018652b79f4231baa70610235fcded048520a4aa3cfaf419849c07b527470

FONT-100 SHA-256
58ccce202250f47306b65663df45faf73be6bdb335b84ca5b65eb797ecde0321
```

離線驗證：

- `62 tests` 通過；
- v53→v54 的 EXE 差異只有前五個座標 byte；
- v52→v54 的 EXE 差異只有表列六個座標 byte；
- v52、v53、v54 的 RESOURCE.GFF byte-for-byte 相同；
- FONT payload 不變；
- 主 MZ relocation 新增 0；
- `autolock=false`；
- `py_compile` 與 `git diff --check` 通過。

## 4. 實機驗證重點

1. Load Game 不閃退，物品頁可正常開啟。
2. `STR/DEX/CON/INT/WIS/CHR` 標籤與數值必須同步上移且仍對齊。
3. PSI、AC 與武器區間距應與 v52 相同，只是整組位置較高。
4. K’Ratchek 的三組武器加 innate/racial 摘要應完整落在底部控制區之前。
5. 在 K’Ratchek、Gerakis 與其他角色之間反覆切換，確認無底部殘影。
6. 回歸右鍵說明卡、底部 hover 名稱與 `autolock=false`。

若能力標籤沒有跟數值一起上移，表示 `0x06F5A0` 的繪圖呼叫不是整組標籤底圖，
屆時只回退／重新定位該單一 anchor，不影響已證明的其他座標與 10px 格線。
