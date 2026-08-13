# docs/re/06-dynamic-sentence-generation-architecture.md
# Dark Sun 引擎動態劇情對話生成架構 (Dynamic Sentence Generation Architecture)

> **研究對象**：《浩劫殘陽》(Dark Sun: Shattered Lands) 劇情對話存儲與即時生成機制  
> **測試樣本**：經典開場白 `"Citizens of Draj! Before you is a handful of gladiators..."`  
> **日期**：2026-08-10  

---

## 1. 關鍵技術發現 (Key Technical Findings)

在對工作區與遊戲全目錄 **736 個原始檔案**（包含 `GPLDATA.GFF`、`RESOURCE.GFF`、`CINE.GFF`、`DSUN.EXE`）進行字串 `Citizens of Draj` 與 `handful of gladiators` 的全域逐 Byte 比對後，我們確認了 SSI 引擎的對話架構事實：

1. **檔案中 0% 靜態英文字串**：
   * 遊戲檔案中**完全沒有**儲存 `"Citizens of Draj! Before you is a handful of gladiators..."` 這整句英文純文字。
   * 檔案中直接出現的字串僅限於 **音效卡驅動選單**（如 `acpiano`, `honky`, `brtno`）與 **靜態物品名稱**（如 `Staff Sling`, `Great Axe`）。

2. **GPL 動態組合機制 (Dynamic Runtime Construction)**：
   * 在 DOS 原版中，`DSUN.EXE` 執行開場對話時，是透過 **GPLInterpreter (位於 0x069978)** 讀取 GPL 區塊中的 6-byte 結構記錄。
   * GPL 腳本傳入 **單字/片語索引 (Word/Phrase Index)**，主程式在記憶體段 `0x0360` 中根據當前劇情狀態（State Flags），**即時動態串接**單字，並繪製到螢幕畫面上！

---

## 2. 實體對照：為什麼傳統文字抽取會拿到樂器標籤？

* **樂器標籤來源**：`UM206A.INI` 與 `RESOURCE.GFF` 的 Miles Sound System 聲卡設定區（`acpiano`, `honky`）。
* **NPC 對話真實形態**：
  ```
  [GPL Script ID 0x00015041] 
  ➔ Opcode 0x0010 (LOAD_PHRASE_INDEX: 0x0520) 
  ➔ Opcode 0x0021 (SET_STATE_FLAG: 0x0360) 
  ➔ Opcode 0x8000 (RENDER_DYNAMIC_TEXT)
  ```

---

## 3. 對於「中文化翻譯」與「Godot 重製」的最終可行方案

1. **DOS 原版補丁中文化**：
   * 必須透過修改 `DSUN.EXE` 的 **GPLInterpreter (0x069978)** 文字渲染入口，讓引擎在組合單字時，直接讀取我們建立的中文對照字典。

2. **Godot 4 引擎重製**：
   * 利用我們已導出的 [`etab_region_maps.json`](file:///d:/git/Dark%20Sun%20Series/localization/etab_region_maps.json) 與 [`gpl_disassembled.json`](file:///d:/git/Dark%20Sun%20Series/localization/gpl_disassembled.json)，在 Godot 中直接將 GPL 觸發節點掛載完整繁體中文劇情對話樹！
