# 《浩劫殘陽2：毀滅者蘇醒》(Dark Sun: Wake of the Ravager) 繁中化交接指南 (handoff_ds2.md)

> **更新時間**：2026-10-29（前期調查，尚未開工）
> **用途**：開始做二代中文化時，新 Session 的 AI 助手先讀這份文件。一代的完整經驗在 [`handoff.md`](handoff.md)；這份只寫二代特有的事，以及哪些一代的成果能沿用。
> **譯名**：中文標題《浩劫殘陽2：毀滅者蘇醒》由使用者提供（2026-10-29）。二代在台灣沒有正式上市（見 5.1），沒有官方中文手冊可依；建立二代權威檔時，**與一代相同的詞彙一律沿用一代** [`docs/名詞權威對照表.md`](docs/名詞權威對照表.md) 的定名，只有二代新出現的名詞才另外定名。

---

## 0. 現況

- **尚未開工**。只做了可行性調查（2026-10-29），沒有建任何二代的組合包、補丁或譯文。
- 結論：二代與一代是**同一套引擎的後續版本**，一代的工具鏈大部分能沿用，最大的工作量是在二代 EXE 上重新找位址。

## 1. 原版檔案

- 位置：`from Steam/games/Dark Sun 2/GAME/RAVAGER/`（Steam 版，遊戲版本 1.1，README 日期 1994-12-14）。
  - **不可修改**這個資料夾；和一代一樣，要先複製到 `scratch_test/` 底下的工作目錄再改。
- 啟動：`run-game.bat` → `mount c .\GAME`、`imgmount d .\game.cue -t iso` → `RAVAGER.BAT` 執行 `DSUN -W0 -L`。部分資料在 CD 映像 `game.bin`，音樂是 `MUSIC/TRACK02.OGG`～（CD 音軌）。
- 主要檔案（26 個 GFF）：

| 檔案 | 內容 | 與一代的差異 |
| --- | --- | --- |
| `DSUN.EXE`（634,416 bytes） | 主程式 | 一代 611 KB；同樣是 Borland C++ 16 位元＋FBOV overlay |
| `RESOURCE.GFF` | 介面、字型、法術說明、文字 | 多了 `DATA`×323、`PLYL`×6、`CBMP`×6；沒有 CMAT／CPAL |
| `GPLDATA.GFF` | 對話／事件腳本、頭像 | GPL×330、MAS×20、PORT×178、TEXT×1；**沒有 `NAME` chunk**（一代的物品名稱表） |
| `OBJEX.GFF` | 物件、生物、物品 | 一代叫 `SEGOBJEX.GFF`；多了 `CBMP`×130、`FNFO`×3、`ALL`×5 |
| `RGN0xx.GFF` | 區域地圖 | 一代是 `RGNxx.GFF`（兩位）；二代是三位數字 |
| `1.FLI`～`5.FLI` | 過場動畫 | Autodesk FLIC；一代是 CINE.GFF 的 BMA |
| `CHARSAVE.GFF`／`DARKSAVE.GFF`／`DARKRUN.GFF` | 存檔 | 同一代 |
| `CHARTRAN.EXE` | 把一代角色轉進二代 | 新的；會讀一代的存檔 |
| `ITEMS.BIN`、`DJ.DAT`、`PATCH.RTP` | 待查 | 新的 |

- 文件：`Documentation/Manual-ENG.pdf`、`Cluebook-ENG.pdf`、`Controls.pdf`。

## 2. 已驗證的結論

### 2.1 字型相同（最重要）

二代 `RESOURCE.GFF` 的 `FONT 100` 與一代**逐位元組相同**（8,299 bytes，sha256 `dbc5528a43f03b8ec5c5da61b53749acbde267c8cc0cc751332f0d78daff46a4`）。

意思是：一代的做法——在 FONT-100 後面附加 16 位元核心、執行期載入 10×10 中文字形、Base94 `^xy` 三字元編碼——在資源這一端可以原樣搬過去。要重做的是 EXE 這一端：二代的繪字、量寬、換行函式在哪裡，以及掛勾點。

### 2.2 EXE 架構相同

MZ 標頭＋Borland C++（1991）＋`FBOV` overlay，和一代一樣。一代的安全修補規則全部適用：先比對原始 bytes、不碰 MZ／overlay 重定位。位址全部要重找，不能沿用一代的偏移。

### 2.3 對話腳本能完整反組譯

用 `vendor/opends` 已經編好的工具：

```sh
cd vendor/opends
G="../../from Steam/games/Dark Sun 2/GAME/RAVAGER"
./target/release/gpl-disasm.exe "$G/GPLDATA.GFF" --all -o <輸出目錄>
# → disassembled 350 GPL/MAS chunks (350 aligned)
./target/release/gff-cat.exe info "$G/RESOURCE.GFF"
./target/release/gff-cat.exe dump-text "$G/RESOURCE.GFF" <輸出目錄>
# → 362 個文字 chunk：MERR×31、SPIN×269、TEXT×62
```

350/350 全部對齊，對話字串直接嵌在 GPL 裡，與一代相同。所以 `tools/build_dialogue_manifest.py`、`tools/compile_gpl_dialogue_patch.py` 這條管線原則上可以沿用，但要檢查二代新增的 opcode。

### 2.4 OpenDS 的二代資源

- `vendor/opends/ds2-patch/`：二代的 bug 修正專案，**尚未發布任何修正**。頭號目標是礦坑電梯當機（`vendor/opends/docs/known-bugs.md` §2.1）。實測當機時先查這份。
- `vendor/opends/docs/dsun-exe-re.md`：有部分 DS1／DS2 的 EXE 對照（例如 FOURCC push 函式在 DS2 是 `0128:04ab`、DS2 完全沒有 CMAT）。
- OpenDS 的 `save-inspect` 能解二代存檔的角色（66 bytes）與物品（23 bytes）子區塊，日後寫二代存檔修補工具時用得到。

### 2.5 yuan-ti 的參考價值

[CalvinRodo/yuan-ti](https://github.com/CalvinRodo/yuan-ti) 是用 Godot 4＋C# 重製的一代引擎，附 Python 解析工具。

- **沒有授權，只能看筆記，不能抄程式碼**。
- 它對二代 GPL 只解得出 258/350（作者說二代是「較新的 VM 版本，有額外 opcode」），不如 OpenDS。
- 有用的是 `.github/instructions/dsun-exe-reference.md`（一代 EXE，約 2,300 行）。位址是一代的，但流程描述很細，可以照著它到二代 EXE 找對應函式：
  - 文字視窗：`PRINT_STRING` 進 0x400 bytes 緩衝區、`END`／`CLOSE` 字串的特殊處理、`WIND 3007`（對話）／`3008`（選項）／`3500`（無頭像）、`EBOX 4002`。
  - 字型：`FONT 100` 載入、繪字（一代 `2E86:06C0`）、量寬（`2E86:07E0`）、高度（`2E86:082C`）、文字顏色 `map[0xFE]`。
  - 角色畫面、創角、法術、物品、戰鬥等各畫面的資料來源。
- 也有 `gff-data-reference.md`、`dark_sun-game-data.md`（GFF 各 chunk 格式）可以互相印證。

## 3. 一代成果的沿用評估

| 一代成果 | 二代能否沿用 | 備註 |
| --- | --- | --- |
| FONT-100 中文核心、10×10 字庫 bank、Base94 | 資源端可直接用 | EXE 掛勾點要重找 |
| GPL 對話抽取／重新編譯（跳躍、觸發器重定位） | 大致可以 | 先確認二代新增 opcode 的參數格式 |
| EXE 安全修補框架（原始 bytes 比對、重定位檢查） | 可以 | 位址全部重找 |
| 名詞權威表、一致性檢查 | 可以 | 另建二代權威檔；一代已有的詞沿用一代，新名詞先補進權威檔再翻 |
| 存檔名字修補工具 | 要改 | 二代存檔格式不同（見 2.4） |
| 物品名稱（一代 `GPLDATA.GFF` 的 `NAME`） | 要重找 | 二代沒有 `NAME` chunk，名稱可能改放在 `OBJEX.GFF` 的 RDFF 或 `ITEMS.BIN` |
| 片頭／片尾圖片（CINE.GFF BMA／BMP） | 不適用 | 二代是 FLI 動畫，若有英文字要另寫 FLIC 工具 |
| 操作改良（遊標熱鍵、智慧遊標、地圖傳送） | 概念可以 | 全部重新逆向；照樣遵守「只新增、不取代」 |
| 整合包與二進位差異補丁 | 可以 | 見 `docs/workflows/release-packaging.md` |

## 4. 建議的開工順序

1. 建工作目錄：把 `RAVAGER/` 複製到 `scratch_test/ds2_...`，確認能用 dosbox-x 啟動（一律用 PowerShell `Start-Process`），CD 映像要掛上。
2. 盤點文字：GPL 對話字串數、`TEXT`／`SPIN`／`MERR`、EXE 內嵌字串，建二代的本地化目錄。
3. 在二代 EXE 找繪字／量寬／換行函式：用一代已知函式的 byte 特徵比對，再用 yuan-ti 的流程描述和 DOSBox-X 除錯器確認。
4. 先做最小驗證：把一段對話改成中文，確認 FONT-100 核心在二代能顯示（相當於一代的 v26 鬥獸場開場）。
5. 再擴大到介面、物品、法術、生物名字。
6. 查新的檔案：`ITEMS.BIN`、`DJ.DAT`、`DATA`／`PLYL`／`CBMP`／`FNFO`，以及 FLI 裡有沒有英文字。

## 5. 待查問題

### 5.1 二代在台灣的發行（2026-10-29 查證）

- 使用者沒找到二代在台灣正式上市的資料。網路搜尋同樣沒有找到智冠或其他代理商發行二代中文版的證據；Steam 版只列英文。
- 標題「毀滅者蘇醒」有出處：德文版標題 *Das Erwachen des Zerstörers*（毀滅者的覺醒），對岸的 CRPG 介紹文章也稱二代為《毁灭者苏醒》。
- 結論：二代沒有官方中文名詞可依，權威檔的規則見文件開頭的「譯名」。日後若找到當年的中文版或手冊，再回頭比對。

### 5.2 其他

- `PATCH.EXE`／`PATCH.RTP` 是不是已經套用？確認目前的 EXE 就是 1.1 版。
- 二代的物品名稱放在哪裡（見第 3 節）。
- 二代有沒有和一代 `-k911` 一樣的除錯模式。
- 礦坑電梯當機等原版 bug 要不要一起修（會牽涉「保留原版行為」的原則，要先問使用者）。
