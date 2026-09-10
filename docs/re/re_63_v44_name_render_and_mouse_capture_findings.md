# v44 物品名稱顯示與滑鼠捕捉實機結果

> 日期：2026-09-10

## 已驗證成果

v44 可從主畫面載入存檔，開啟物品欄，並把 NAME-1 的 Base94 中文名稱解碼成
FONT-local 動態 glyph。`長劍` 的兩個字會正確載入兩個 10x10 records；底部 hover
列可顯示 `BONE 長劍`。

FONT 核心必須以 GNU assembler 的 `OFFSET label` 取得內部標籤位址。裸 label
會被編成 DS-relative memory operand，曾使核心回傳 `DS:25FC` 的內容而非 buffer
位址。v43 起已修正並由實機返回點驗證。

## 中央卡片與右側欄重疊

`2143:0A40` 傳給 formatter `339E:016D` 的參數正確包含完整 far pointer；格式字串
為 `%C%C%C%s`。在 `%s` 迴圈 `339E:02E8..0302` 中，兩個 transport bytes 都被
逐字處理，且 `SI` 確實水平前進。

問題是 `11A4:59C1` 對這條 formatter 路徑固定回傳 `DI=7`，而動態中文字形寬度為
10 pixels，因此相鄰 glyph 覆蓋 3 pixels。這不是行高或換行問題。

v45 曾嘗試把 10x10 raster 壓成 7x10；實機中文字嚴重失真，右鍵說明卡也無法穩定
出現，因此方案已拒絕並從工作中的建置程式撤回。後續應保留 10x10 glyph，只在
物品名稱 formatter 路徑補足水平 advance。

## 右鍵說明卡與 autolock

`autolock=false` 時，乾淨啟動後右鍵可能無法叫出說明卡；用其他視窗遮住 DOSBox-X
再切回遊戲後，右鍵會恢復。bridge 當時回報 `captured=false`、`autolock=false`、
`mode=absolute`。

只把 `base.conf` 改為 `autolock=true` 的 v44 A/B，在不切換視窗的情況下已實機
確認右鍵說明卡立即出現。不過使用者會同時進行多項工作，自動捕捉會妨礙視窗切換，
因此後續 NAME-slot candidate builder 仍維持 `autolock=false`。右鍵未回應時，暫時以
切換至其他視窗再回到 DOSBox-X 來重置焦點；另尋不需捕捉滑鼠的輸入修正。
