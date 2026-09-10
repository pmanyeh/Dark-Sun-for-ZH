# v53 右側攻擊欄 compact profile candidate

> 日期：2026-09-10
>
> 狀態：完成動態容量量測與離線建置；v53 尚待使用者實機驗證。

## 1. v52 動態重現結果

以 DOSBox-X-AI 的窄域 breakpoint 監測共用物件文字 wrapper `2143:0A40`。
監測器不寫 guest RAM、不啟用 execution trace；每輪均自動刪除自己的 breakpoint，
最後確認 breakpoint list 為空且 guest `running=true`。

K’Ratchek 的右側攻擊欄實際序列為：

```text
caller       X    Y    內容
6045:2B9C  236  129    第一 attack block 名稱
6045:2CD4  236  139    第一 attack block 數值
6045:2B9C  236  149    第二 attack block 名稱
6045:2CD4  236  159    第二 attack block 數值
6045:2B9C  236  169    第三 attack block 名稱
6045:2CD4  236  179    第三 attack block 數值
5B7C:2A85  236  189    innate/racial attack 摘要
```

每列為 10px，因此最後一列實際使用約 `Y=189..198`。底部控制區約從邏輯
`Y=181` 開始；v52 並非越過 200px 畫面，而是文字侵入另一個 invalidation 區域。
角色切換後該區域不一定由右欄背景重畫，所以會留下殘影。

Gerakis 的 innate-only 基準只有 caller `2A85` 的一列，位於 `Y=129`。

## 2. 靜態路徑確認

主攻擊列表函式位於 file `0x0726AC`：

```text
0x072773  imul ax, ax, 10   ; 子函式回傳行數 × 10
0x072776  add [bp+0E], ax   ; 推進下一 attack block
0x07296F  add [bp+0E], 10   ; 名稱到數值列
```

上層 file `0x06F6A5` 只把固定 `(X=236,Y=129)` 傳入，沒有現成 attack-count
條件可供低風險分支。若實作「只有超量時 compact」，需要新增計數與 code-cave
跳轉，風險高於本輪最小候選。

另發現 file `0x072858` 仍有一條 `+7`，但本次 K’Ratchek 重現沒有走到；不可在
缺少實際 caller 證據時順手修改。

## 3. v53 最小修補

保持所有已驗證的 10px 局部格線，只把 weapon section 固定起點上移到 AC 下一列：

```text
file 0x06F6A5  66 68 EC 00 78 00 -> 66 68 EC 00 6D 00
                                original Y=120    v53 Y=109
```

v52 在同一位置為 `Y=129 (0x81)`。v53 最壞七列為：

```text
109, 119, 129, 139, 149, 159, 169
```

最後 glyph 使用 `Y=169..178`，完整留在底部控制區 `Y=181` 之前。AC 位於
`Y=99..108`，因此不會與第一列重疊；代價是一般角色的 AC 到武器區空白由 30px
縮成緊鄰的 10px 格線。這是局部 compact profile，不是恢復全域 7px。

## 4. Build checkpoint

```text
scratch_test/cjk_display_staging_v53_compact_item_panel

DSUN.EXE SHA-256
771d0ed4d2b4239465fedd3e0df5c45d24bfc7a29e4b665387ee491b5fcc2724

RESOURCE.GFF SHA-256
d42018652b79f4231baa70610235fcded048520a4aa3cfaf419849c07b527470
```

v52→v53 精確比對：

- EXE 長度同為 611408 bytes；
- 唯一差異為 file `0x06F6A9`：`81 -> 6D`；
- RESOURCE.GFF byte-for-byte 相同；
- `autolock=false`；
- 主 MZ relocation 沒有新增項目；
- GFF 共 1205 chunks，僅目標 FONT-100 改變，1203 個 non-target chunks 不變，
  另允許 GFFI container metadata；
- `61 tests` 通過，另通過 `py_compile` 與 `git diff --check`。

## 5. 實機驗證順序

1. 啟動 v53，Load Game，確認不閃退。
2. 開 K’Ratchek 物品頁，確認七列落在 `109..169` 且文字不重疊。
3. 在 K’Ratchek 與 Gerakis 之間反覆切換，確認底部按鈕區不再留下文字殘影。
4. 檢查一般一件武器、雙持、innate-only 的 AC/武器間距是否可接受。
5. 回歸右鍵說明卡、底部 hover 名稱與 `autolock=false` 操作。

若 v53 的 compact 間距不可接受，下一步才設計 attack-count-aware code cave；不要
以改回 7px 行高解決容量。

## 6. 監測工具

新增 `tools/monitor_item_panel_layout.py`。預設只記錄主物品右欄與替代細節 overlay
的已知 caller offsets；`--all-callers` 可用於重新盤點。它在成功、timeout 或中斷時
都會移除自己的 `2143:0A40`／`2143:0A6A` breakpoint 並恢復 guest 執行。
