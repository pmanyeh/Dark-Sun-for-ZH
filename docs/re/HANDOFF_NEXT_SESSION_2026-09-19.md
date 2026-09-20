# 《浩劫殘陽》繁中化：下一個 session 交接（2026-09-19，對話選項行距突破版）

## 0. 當前工作基準與背景狀態

- **目前基準 Checkpoint**：
  ```text
  scratch_test/cjk_display_staging_v76_arc_menu_options
  ```
- **背景脈絡**：
  - VIEW CHARACTER 屬性介面已於 v75 正式告一段落（見 `re_95`）。
  - 本階段重心轉移至**對話選項中文化（Dialogue Options）**。
  - v76 staging build 匯入了 GPL-2/3/4/5/6/9/162/195 對話選項翻譯，並在實機點亮了 GPL-4@0x03BC 六選一選單（"WHAT DO YOU SAY?"）。
  - 遇到的 Blocker：**選項清單多行文字在垂直方向上緊密貼合、互相重疊**。先前 `re_96` 嘗試使用 `--ebox-line-gap` 與 EBOX line table 修補，但完全無效。

---

## 1. 核心突破（詳見 `docs/re/re_97_dialogue_menu_line_spacing_analysis_and_patch_strategy.md`）

已徹底查明控制對話選項行距的根本機制：

### 1.1 系統架構真相
- 對話視窗為**複合視窗**：
  - 上半部 NPC 對話文字：**`EBOX` 控制項**（位於二進位段 `0x31390`，受 `EBOX_STORE_LINE_HEIGHT` 控制，`--ebox-line-gap` 僅作用於此）。
  - 下半部選項列表：**`MENU` 控制項**（位於二進位段 `0x2C450`）。
- **`MENU` 擁有完全獨立的排版與繪製邏輯**，完全不查閱 EBOX 的 line table。

### 1.2 核心指令與檔案偏移
- **排版函式**：`GuiMenuLayout`（檔案偏移 `0x2C51C`）。
- **字型高度**：`0x2C61F` 呼叫 `FontGetHeight([0xa06d])` 取得 `FONT-100` 高度（固定為 `9`），存入 `[bp - 6]`。
- **行距累加核心**（二進位檔案偏移 `0x2C713` ~ `0x2C719`）：
  ```asm
  0x2C713: 8B 46 FA        mov ax, [bp - 6]   ; AX = 9 (font_height)
  0x2C716: 05 02 00        add ax, 2          ; ★★★ 核心硬編碼常數：+2 行間距 ★★★
  0x2C719: 01 46 F4        add [bp - 0x0c], ax; current_Y += (font_height + 2)
  ```
- **重疊原因**：
  - 英文大寫字母僅 6~7px 高，步進 11px（$9 + 2$）有 4~5px 呼吸空間。
  - 中文 16x15 點陣漢字實體高達 10~11px，在 11px 步進下**留白為 0px**，上下行字元筆劃與陰影直接黏連重疊。

---

## 2. 下一個 Session 的直接執行指南 (Action Playbook)

下一位接手者**無須重新逆向分析**，請直接依序執行以下步驟：

### 步驟一：實施 Patch 測試
在 `scratch_test/cjk_display_staging_v76_arc_menu_options/GAME/DARKSUN/DSUN.EXE` 上實作補丁：
- **修改位置**：二進位檔案偏移 `0x2C716`
- **原始位元組**：`05 02 00` (`add ax, 2` $\rightarrow$ 步進量 11px)
- **測試候選值**：
  - 候選 1：改為 `05 04 00` (`add ax, 4` $\rightarrow$ 步進量 13px，字間距留白約 2~3px)
  - 候選 2：改為 `05 05 00` (`add ax, 5` $\rightarrow$ 步進量 14px，字間距留白約 3~4px，最接近英文舒適度)

### 步驟二：實機啟動與測試 (DOSBox-X)
1. 啟動 DOSBox-X 並載入存檔或開新遊戲。
2. 與開場 NPC（如地牢同伴）對話，觸發包含多行選項的對話選單（如 GPL-4@0x03BC 六選一選單）。
3. **驗證清單**：
   - [ ] 中文選項上下行是否明顯分開、字跡清晰不再互相重疊。
   - [ ] 按數字鍵 `1` ~ `6` 進行選項選擇，確認快捷鍵響應與邏輯對應是否正確。
   - [ ] 滑鼠懸停（hover）高亮與點擊選取是否正常。
   - [ ] 最末項（第 6 項）是否完整顯示在對話視窗內、選單外框有無發生不正常的下緣裁切。

### 步驟三：整合進工具鏈與建立新 Checkpoint
- 若驗證通過，將選單行距常數整合至建置工具（如 `tools/patch_dsun_scratch_cache.py`，新增 `--menu-line-gap` 參數）。
- 建立並提交新 checkpoint（例如 `staging_v77_menu_line_spacing`）。
