# v55 右側資訊區整組上移 30px candidate

> 日期：2026-09-10
>
> 狀態：v55 已由使用者實機確認右側七列完整收進面板，可作為下一階段基準。

## 1. v54 實機結果

使用者確認 v54 的整組上移方向正確，能力標籤與數值仍對齊；但 K’Ratchek 最後一列
innate/racial 摘要 `<1D4+8>` 仍壓到右側底部控制區上框。畫面顯示約需再上移一個
10px 格線，不能把 v54 視為完成版。

## 2. v55 調整

v55 將 v54 的完整資訊區再上移 10px；相對 v52 共上移 30px：

```text
區域                    v52 Y       v54 Y       v55 Y
能力標籤／底圖起點       53           33           23
六項能力數值起點         53           33           23
PSI/第一組資訊           99           79           69
PSI 數值                 99           79           69
AC/第二組資訊           113           93           83
武器區                  129          109           99
```

最壞七列武器資訊改為：

```text
99, 109, 119, 129, 139, 149, 159
```

最後 10px glyph 約使用 `Y=159..168`，應完整留在實機畫面約 `Y=173` 的底部控制區
上框之前。10px 行距與各子區塊相對距離均不變。

## 3. Build checkpoint

```text
scratch_test/cjk_display_staging_v55_shifted_item_panel_30px

DSUN.EXE SHA-256
c27f6f2105099a993f3b2171ef4aa47c5a739053697ca73f4bdd6c4fc7753b07

RESOURCE.GFF SHA-256
d42018652b79f4231baa70610235fcded048520a4aa3cfaf419849c07b527470

FONT-100 SHA-256
58ccce202250f47306b65663df45faf73be6bdb335b84ca5b65eb797ecde0321
```

離線驗證：

- `62 tests` 通過；
- v54→v55 只有六個右欄 Y 座標 byte，各自 `-10`；
- RESOURCE.GFF byte-for-byte 相同；
- FONT payload 不變；
- 主 MZ relocation 新增 0；
- `autolock=false`；
- `py_compile` 與 `git diff --check` 通過。

## 4. 實機驗證

1. Load Game 與開啟物品頁不得閃退。
2. 確認頂部能力標籤沒有碰到角色名稱框或被裁切。
3. 確認能力標籤／數值、PSI、AC 與武器資訊仍對齊。
4. 確認 `<1D4+8>` 整列及字形下緣位於底部框線上方。
5. 在 K’Ratchek 與其他角色間反覆切換，確認沒有殘影。

## 5. v55 使用者實機結果

使用者提供的 K’Ratchek 物品頁截圖確認：

- `STR/DEX/CON/INT/WIS/CHR` 六列完整顯示，頂端沒有碰到角色名稱框；
- PSI 與 AC 區塊完整顯示；
- 三組武器名稱／數值仍維持 10px 格線，沒有上下重疊；
- 最後 innate/racial 摘要 `<1D4+8>` 的字形下緣完整位於底部控制區上框之前；
- 整組資訊的視覺位置獲使用者確認為 OK。

因此 v55 取代 v52、v53、v54，成為後續 UI／文本中文化工作的唯一可玩基準。
v47/v48 的 global-height 路線仍維持否決，不得重新引入。
