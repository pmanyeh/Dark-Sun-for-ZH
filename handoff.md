# 《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands) 繁中化交接指南 (handoff.md)

> **產生時間**：2026-09-21 23:01（第 0、四節更新於 2026-09-25）  
> **交接目的**：為下一輪重開 Session 的 AI 助手提供完整無縫的專案背景、歷史數據、技術規範、標準操作 SOP 與接續目標，確保繁中在地化推進不中斷。

---

## ⚠️ 0. 最新狀態（2026-09-25 更新，新 Session 請先讀這一節）

### 0.1 現況

- **可玩版本**：`scratch_test/cjk_display_staging_v117_approach_walk_mode`（使用者已實機確認，2026-09-25）。
- **操作改良（v107～v117，re_104）**：
  - 遊標模式熱鍵：空白鍵＝行走、`A`＝攻擊、`S`＝觀察，`T`＝動畫開關（原本在 `A`）。
  - 智慧遊標（非戰鬥時）：
    - 行走遊標點物件（NPC、門、箱子，不含隊員）：相鄰就互動；不相鄰就走過去，走到之後自動互動。
    - 按住 Ctrl 點：只移動，不互動。
    - 觀察遊標點太遠或視線被擋的東西：走過去，走到之後自動互動（戰鬥中維持原版訊息）。
    - 靜態物件（石棺、草堆）會走到旁邊的空格。
    - 懸停在可互動的物件上時，行走遊標會換成觀察圖示。
    - 攻擊遊標點搆不到的目標（沒有遠程手段）：走過去再攻擊。遠程攻擊照原版。
    - 從觀察／攻擊遊標開始「走過去」時，會先切回行走模式（非行走模式下世界是暫停的）。
  - 建置選項：`--cursor-hotkeys`、`--smart-cursor`（都需要 `--view-ui`）。
  - 下一步：玩家用的操作說明。
- **本輪總整理**：`docs/re/re_104_cursor_mode_hotkeys_investigation.md`（操作改良）、`docs/re/re_103_v90_v106_menu_titles_and_exe_strings.md`（字串翻譯）。
- **已中文化**：
  - 全部對話（re_99）
  - 背包／VIEW CHARACTER 的標籤、性別、種族、陣營、職業（含多職業）
  - 物品名稱（NAME-1）
  - 物品材質字首（re_100、re_101）
  - 對話選單標題、漏抽的短片段、是非選單（re_103）
  - EXE 內的訊息框、存讀檔提示、戰鬥彈出框、法術／靈能名稱、頭像狀態、USE 按鈕（re_103）
- **v89 的修正**：第三職業顏色、VIEW CHARACTER 下半部四行行距（re_102）。
- **最新 commit**：見 `git log`。v90～v106 分兩次 commit，並已 push；v107～v117 另有三次 commit。
- **v90（2026-09-24，已確認）**：`scratch_test/cjk_display_staging_v90_fragments`
  - 對話裡殘留的 `he`、`is` 之類英文，原因是 opends 抽取時跳過了 3 字元以內的 print string，
    這些字串從來沒進 catalog。
  - 全部 250 個 GPL/MAS chunk 重新反組譯比對，漏網的共 155 處：
    - 115 處寫進 `localization/catalog/dialogue_fragment_overrides.json`，以 chunk+offset 為鍵逐處翻譯，
      空字串代表不印。
    - 40 處保留英文：GPL-20 防拷問答的比對字母，以及排版用的空白。
  - 編譯器新增 `--fragment-overrides` 選項。
  - GPL-135 的「匕首 (不)佩服你的實力」兩條譯文改了詞序。
- **v91／v92（2026-09-24，已確認）**：`scratch_test/cjk_display_staging_v92_title_y`（v91 實機顯示正常，但中文標題和第一個選項重疊 1～2px；v92 把中文標題改畫在 y=2，英文仍是 y=4，待確認）
  - 對話選單標題（`WHAT DO YOU SAY?` 等 21 條）翻成中文。
  - 標題繪製程式在 overlay `0x7D80A`：
    - 先 `strupr(ds:5504)` 轉大寫。
    - 再經 `0150:016D`（`339E:016D` formatter，`"%C%C%C%s"`）繪製，這個 formatter 不解碼 Base94。
  - 修補方式（`view_ui_layer.VIEW_UI_EXE_PATCHES` 最後兩筆）：
    - `strupr` 呼叫的 offset 改指向它自己的 `retf`（`0:39CF`）。
    - `0x7D818～0x7D83A` 換成 tag `FF81` redirect。FONT 核心的 `menu_title_entry` 會先檢查標題：
      - 含 `^`：解碼到 name-slot。
      - 純英文：自己轉大寫，照原樣傳下去。
    - 最後重新 push 原本的 formatter 參數。
  - name-slot 只有 10 格，所以**標題的相異中文字（含全形標點）不能超過 10 個**。
    本輪因此縮短了 5 條標題譯文。
  - 編譯器新增 `--translate-menu-titles`，封包會記錄 `menu_titles_translated`。
    組合包沒有 `--view-ui` 時會拒絕建置。
  - withheld 只剩 `END`、`CLOSE` 兩筆。
- **v106（2026-09-25，使用者已確認）**：`scratch_test/cjk_display_staging_v106_status_lower`
  - 使用者要求狀態字再往下 5px，離頭像框下緣 1px：y＝+26（`0x6BFB2` = `1A`），中文實際畫在 +28～+37。
- **v105（2026-09-25，位置偏高，由 v106 微調）**：`scratch_test/cjk_display_staging_v105_status_in_frame`
  - v104 的 HP 放在框內時，數字碰到頭像框、被框的顏色吃掉；三位數 HP 也會超出框。
  - 改用使用者的第二個提議：
    - HP 還原到 +38。
    - 兩個字的狀態移進頭像框底部：y＝+21（`0x6BFB2`），中文實際畫在 +23～+32；
      x 基準 1→5（`0x6BFB6`），往右 4px。
- **v104（2026-09-25，HP 被框線吃掉，改為 v105 的做法）**：`scratch_test/cjk_display_staging_v104_portrait_rows`
  - 背包畫面的單欄頭像列（overlay `0x6BEE6` 起）：
    - 頭像 y＝si×48+6；HP 原本在 +38（立即值 `0x6BF7A`），狀態原本在 +44（`0x6BFB2`）。
    - 兩行只差 6px，放不下 10px 高的中文字。
  - 當時的做法：HP 移進頭像框內（+27），狀態移到原本 HP 那一行（+38）。已由 v105 取代。
  - 其他三個畫面（USE／VIEW 等 2×2 頭像，呼叫 `0580:0066` 的 `0x7E725`、`0x87E65`、`0x89F86`）空間夠，沒有改。
  - 頭像狀態由 overlay 第 25 段第 14 個入口 `0x71D8B` 繪製：先置中，再經 `191F:0A40` 畫出。
- **v103（2026-09-25，VIEW 已確認；背包頭像空間不足，由 v104 處理）**：`scratch_test/cjk_display_staging_v103_status_layout`
  - v102 的中文顯示正常，但有兩個位置問題：
    - 背包的狀態只比 HP 低 7px，10px 高的中文字會蓋到 HP。
    - VIEW 的置中位置偏左。
  - 量寬度函式 `191F:0401`：`0x1E9F6～0x1EA06` 換成 tag `FF86` redirect，回到 IP `042A`；空指標回到 `0437`。
    中文會先解碼成字形碼，迴圈量到的就是實際畫出來的寬度。
  - `text_draw_entry`：中文的 y 座標 +2。
  - v101 的其他部分已確認：USE 切換按鈕、靈能分類、等級按鈕。
  - **待驗證**：學法術卷軸的「學習」「第3級」，使用者目前還沒有可以測試的存檔進度，之後遊玩時再確認。
- **v102（2026-09-25，中文正常、位置偏移，已由 v103 修正）**：`scratch_test/cjk_display_staging_v102_draw_text`
  - v101 實機測試時，頭像下方狀態顯示成亂碼。
  - 狀態透過 `11DC` 表取得，取法是角色資料 +0x1C 當索引；有兩處使用：
    - 背包：`0x5FD51` → `0090:0A40`，實際是常駐 `191F:0A40`（檔案 `0x1F030`）。
    - VIEW／USE：`0x71DD4`，先 strncpy，再量寬度置中。
  - `191F:0A40` 是 47 bytes 的 draw_text 包裝函式：用 `"%C%C%C%s"`（ds:0D8F）呼叫 339E:016D，不會解碼。
  - 修補方式：
    - `0x1F033～0x1F050` 換成 tag `FF84` redirect，回到 `0x1F051`。
    - FONT 核心的 `text_draw_entry`：中文就解碼成 name-slot 字形碼，英文照原樣傳下去。
  - 這個包裝函式是常駐的，其他呼叫者（`USEABLE BY:`、`HD: %d` 等）也能直接顯示中文。
  - 待觀察：`0x71DD4` 那條路徑是用 Base94 原始 bytes 量寬度，中文的置中位置可能會偏。
- **v101（2026-09-24，試驗版；頭像狀態亂碼，已由 v102 處理）**：`scratch_test/cjk_display_staging_v101_use_labels`
  - DGROUP far pointer 表（段 `4356`）引用的字串：
    - `11DC`（29 筆）指向頭像下方狀態（Okay…）、職業名、USE 切換按鈕（MAGE/CLERIC/PSlONlC）。
      切換按鈕共用職業名的字串。
    - `30FA`（4 筆）指向靈能分類（念動／精神／感應／傳送）。
    - `3112`（Kinetics 結尾的 NUL）被 push 當空字串使用，所以保留原位。
  - 學法術卷軸：LEVEL %d／選擇法術，／學習／已學會。USE 畫面也有一個 LEVEL %d。
  - `exe_text_layer` 新增兩個功能：
    - `pointer_tables`：字串搬動後，表裡的偏移跟著改（段值那個 word 有 MZ 重定位，不動）。
    - 允許多筆指向同一個字串。
  - 試驗目的：這些字串的繪製路徑還沒實機確認過（頭像狀態、切換按鈕、分類按鈕）。
  - 卷軸的 EXIT 不在 EXE：v98 已經把 EXE 唯一的 EXIT 改成「離開」，卷軸上仍是英文，應該在視窗資源（WIND）裡。
  - 已確認：USE 資訊列的「19✓ 8👢」分別是成功門檻（體質 22 − 3）和射程，
    `^`、`|` 在 FONT-100 裡是打勾和靴子圖示，保留不翻。
- **v100（2026-09-24，使用者已確認）**：`scratch_test/cjk_display_staging_v100_spell_names`
  - 法術／靈能名稱（USE 畫面下方資訊列、學法術卷軸）。v99 試驗證實這兩處的繪製路徑會解碼。
  - **譯名一律依詞彙表（智冠定名）**，使用者 2026-09-24 決定：
    - 資訊卡（SPIN）原本另有一套譯名（如 迷霧牆、解離術），共 118 張已改成詞彙表定名。
    - 其中 4 張的內文是一般用語（冰牆、魔法石、治療疾病），另外手動修正，不照替換結果。
    - NAME-1 物品名在詞彙表裡本來就另外定名（如 Ego Whip 物品＝自我之鞭），所以不改。
  - 名稱放在 DGROUP `254E～2EBA`，只由兩張資料表引用：
    - 法術表：檔案 `0x4512E`，138 筆，每筆 7 bytes，名稱位址在 +3。
    - 靈能表：檔案 `0x44F96`，34 筆，每筆 8 bytes，名稱位址在 +0。
  - 連結器合併了一些字尾，例如 ARMOR＝FLESH ARMOR 的尾巴，INVISIBILITY、SHIELD、STRENGTH、POISON 也一樣。
  - 做法：
    - `exe_text_layer.spell_block_patch` 讀 `localization/catalog/exe_spell_names.csv`（168 條）。
    - 整段重新排列，改寫 171 個表格位址，還剩 432 bytes 空間。
  - mapping 新增 10 個字，所以重建了 bank v22、對話封包 v10、資訊卡包 v4。
    舊字的 ID 和字元都沒有變。
  - 詞彙表補上召喚小型風／火／土／水元素、召喚風／火／土／水元素。
- **v98（2026-09-24，已確認）**：`scratch_test/cjk_display_staging_v98_combat_popup`
  - 戰鬥「結束角色行動」彈出框（常駐 `0x1DB1F`）：
    - 流程：先 `sprintf` 出 `END %Fs's MOVE`，再開啟 `41B4:0025` 確認框，按鈕是 GUARD／WAIT／END TURN。
    - 44 bytes 要放進五條字串，所以譯成「%Fs回合／回合／防守／等待／結束回合」。
  - 確認框的按鈕文字經 `2A1D:07FA` 設定（和對話選項相同，會解碼）。
    `4211:00B1`／`00B6` 只是計算彈出框座標，盤點腳本的「後面最近的 far call」在這裡配錯了。
  - sprintf 格式字串（`00A8:0002` = 常駐 `1D53:0002`）裡，結果會送進訊息框的 10 條也已翻譯，
    例如「%Fs升級了」「%Fs被魅惑」「找到 %u$」。
- **v97（2026-09-24，使用者已確認）**：`scratch_test/cjk_display_staging_v97_window_text`
  - v96 實機測試存檔時，提示框顯示成亂碼（Base94 bytes 被逐字畫出，`[` `{` 變成材質字形「木製」）。
  - 訊息框的文字都經過 overlay 第 25 段的 `0x7045D`（stub `0580:005C`，執行期段 `4272`）。它的流程是：
    - 字串超過 30 bytes 就在第 30 byte 寫入 NUL。
    - `strncpy(bp-28h, 字串, 31)`。
    - `strupr`（`0:2FC4`）。
    - 逐字繪製，不會解碼。
  - 修補方式：
    - `0x704AB～0x704BD` 換成 tag `FF82` redirect，回到 overlay IP `06EE` 那個沒動過的 strncpy。
    - FONT 核心的 `status_text_entry` 把中文解碼成 name-slot 字形碼，字形碼都不是 a–z，strupr 不會改到。
  - 限制：
    - 每則訊息最多 10 個相異中文字，而且不能超過 30 bytes。
    - 字形格和物品名稱共用，訊息顯示期間如果背包重畫，字形可能被換掉。
- **v96（2026-09-24，實機亂碼，已由 v97 修正）**：`scratch_test/cjk_display_staging_v96_message_boxes`
  - EXE 字串第二批：確認框與提示訊息，共 26 個區塊、約 55 條，全部寫在 `tools/exe_text_layer.py`。
  - **overlay 段號怎麼查**：執行期讀記憶體最可靠。
    - 例如 overlay 程式碼裡的 `04D0`，載入後變成執行期 `49D8`，減掉 `0x824` 就是 `41B4`。
    - `41B4` 是 overlay 第 3 段的 stub 描述區，用 ovr-map 可以解出：
      - `:0020` → `0x561D7`（請稍候）
      - `:0025` → `0x54F21`（有按鈕的確認框）
      - `:002A` → `0x5536E`（單行訊息）
    - 訊息文字經 `0580:005C` 寫進控制項 `2C06`。
    - 段號和檔案位置之間沒有固定換算關係（`0x140`→`2A1D` 只是巧合），不能直接套公式。
  - `exe_text_layer` 會自動找出所有 `push ds; push <舊位址>` 並改寫。它也會拒絕兩種情況：
    - 區塊中間有沒登記的引用。
    - 碰到 MZ 或 overlay 重定位。
  - `OKAY`（`1BD5`）的 push 被 overlay 重定位表登記，所以不搬移，只在原位譯成「好」。
  - 暫緩處理：
    - `INACTIVE CHARACTER`（`1AC1`）和 `CANCEL`（`1B7F`）也被其他路徑使用。
    - `LOAD`（5 bytes）原位放不下，`NEW`／`ADD` 也還沒處理。
  - 字型 mapping 沒有「刪」「磁」，改用「清除」「存檔空間」。
- **v95（2026-09-24，已確認）**：`scratch_test/cjk_display_staging_v95_variable_reads`
  - 使用者看到「Let's change the subject.」選項是英文。
    - 它是 MAS-99 寫進 GSTR[7] 的字串，選單用變數讀取。
    - 舊的候選清單條件把「有變數讀取引用」的單元整條排除，共 92 條（13,194 → 13,286 單元，共 13,996 處）。
  - 編譯器新增 `--all-translated`，並略過 `text:*` 引用：這種引用沒有字串資料，字串在 `string copy` 那一處。
  - 存檔改寫移到 `tools/patch_save_gstr.py`，並涵蓋 GSTR[7]。
- **v93／v94（2026-09-24，使用者已確認選項長度與是非選單正常）**：`scratch_test/cjk_display_staging_v94_yes_no`
  - **選項長度上限 49 bytes**：
    - 對話處理程式把選項存在 DGROUP `0x5537 + n×0x33` 的 51 bytes 格子裡。
      超過 50 bytes 的選項會在第 49 byte 截斷（`0x7CF1B`）。
    - 繪製時用 `strncpy(buf, 選項, 50)`（`0x7D86E`），剛好 50 bytes 就沒有 NUL，會印出堆疊垃圾。
    - 使用者看到「唾棄他」後面三個亂碼字，就是這個原因。
    - 已把 278 條選項縮短到 ≤49 bytes，也就是 2 個空白加最多 15 個中文字。
    - 編譯器遇到超長選項或標題會丟 `MenuTextTooLong`。它刻意不是 `ValueError`，
      否則會被 main 當成「跳過 chunk」吞掉。
  - **是非選單**（EXE 字串第一批）：新模組 `tools/exe_text_layer.py`。
    - `0x6B7BD` 用 DGROUP `1600`（Answer Yes or No）、`1611`（Yes）、`160E`（No，和前一句共用尾巴）組選單。
    - 對話處理程式用 `stricmp(ds:5504, ds:1F61 "answer yes or no")` 辨認是非選單，所以兩處要翻成相同的中文。
    - 「否」搬到 `160D`，`push 160Eh` 改成 `push 160Dh`。
  - **EXE 字串盤點**：
    - 用 `push ds; push <偏移>` 找引用，再看後面最近的 far call，依呼叫目標分組。例如：
      - `00A8:0002`：48 條，格式化訊息。
      - `04D0:0020/0025/002A`：約 60 條，確認框、YES/NO/CANCEL、NO MEMORY 等。
      - `0578:0070`：商店。
      - `4211:00B1`：戰鬥。
    - overlay 程式裡 far call 的段值不能用 `0x5400+段×16` 直接換算（例如 `0x140`→`2A1D`、`0x150`→`339E`），
      要到執行期確認實際函式。

**下一輪目標：繼續翻譯程式內的字串**。已完成的部分見上方 v90～v106 與 re_103。建議順序：

1. **視窗資源（WIND，在 RESOURCE.GFF）裡的按鈕**：
   - 學法術卷軸的 EXIT、背包的 DROP／SPLIT 等。它們不在 EXE，要找出 WIND chunk 的文字格式。
2. **尚未盤點的 EXE 字串**：遊戲選單（GAME MENU、MUSIC ON…）、商店（STORE、NO DEAL!、SOLD!）、
   背包下方提示列（`SELECT K'RATCHEK`、`HIT POINTS: CURRENT/MAX`）。每一條都要先確認繪製路徑：
   - 會解碼的路徑：直接加進 `exe_text_layer`。
   - 經過 `191F:0A40` 或 `0580:005C` 的：已經會解碼。
   - 其他不解碼的：用 FONT 核心 tag redirect，做法見 re_103 §6。
3. **暫緩的字串**：`INACTIVE CHARACTER`、第二個 `CANCEL`（其他路徑也在用），以及 `LOAD`／`NEW`／`ADD`（原位放不下）。
4. **學法術卷軸（2026-09-25 v111 實機截圖，待處理）**：
   - 下方兩行說明文字是亂碼：Base94 的 `^` 被畫成打勾、`[` 被畫成材質字形「木製」。這條路徑不會解碼。
     要先找出繪製路徑，可能是 v101 的「選擇法術，」或法術名稱。
   - 左下角的「第1級」有解碼，但顏色很淡。要確認原版的 `LEVEL 1` 是否也是這個顏色（可能是停用狀態的按鈕）。
   - `EXIT` 仍是英文（在 WIND 裡，見第 1 項）。
   - 使用者要求：操作改良（re_104）告一段落之後再處理。

右側直排的 `MORE` 是圖片，使用者說先不處理。

### 0.2 重建 v117（`scratch_test/` 在 `.gitignore` 裡）

```bash
# 0) 舊的候選清單腳本：已改用編譯器的 --all-translated（步驟 3），這段不再需要
python - <<'EOF'
import json
from collections import defaultdict
occs = json.load(open('localization/catalog/dialogue_occurrences.json', encoding='utf-8'))['occurrences']
units = json.load(open('localization/catalog/dialogue_units.json', encoding='utf-8'))['units']
translated = {u['unit_id'] for u in units if u.get('translation_zh_tw', '').strip()}
by_unit = defaultdict(list)
for o in occs:
    if o.get('unit_id'):
        by_unit[o['unit_id']].append(o)
ok = sorted(uid for uid in translated if by_unit.get(uid) and all(
    not o.get('unresolved') and str(o.get('kind', '')).strip().upper() in ('GPL', 'MAS')
    and o.get('source') == 'inline' and o.get('sub_type') == 'compressed'
    for o in by_unit[uid]))
open('scratch_test/all_translated_unit_ids.txt', 'w', encoding='utf-8').write('\n'.join(ok))
print(len(ok))   # 13194
EOF

# 1) mapping（已 commit；只有新增字元時才重跑，三個 catalog 都要給）
python tools/cjk_localization_pipeline.py inventory \
  --catalog localization/catalog/localization_manifest.csv \
  --catalog localization/catalog/fixed_ui_labels.csv \
  --catalog localization/catalog/exe_spell_names.csv

# 2) 字型 bank（mapping 有新字時才重建）
python tools/cjk_localization_pipeline.py build-banks --mapping localization/cjk_mapping.json \
  --output scratch_test/formal_cjk_fusion_10x10_v22_spell_names --font Fonts/Fusion_Pixel_10px.ttf \
  --font-size 10 --pixel-width 10 --height 10 --advance 10 --threshold 64 --fit-mode pixel-aligned

# 3) 對話封包 → 疊上 NAME-1
python tools/compile_gpl_dialogue_patch.py \
  --all-translated \
  --fragment-overrides localization/catalog/dialogue_fragment_overrides.json \
  --translate-menu-titles \
  --output scratch_test/gpl_full_from_pristine_v10_spell_mapping
python tools/compile_gff_name_records.py \
  --prior-package scratch_test/gpl_full_from_pristine_v10_spell_mapping/gpl-dialogue-patch.json \
  --output scratch_test/gpl_full_v10_name_records

# 4) 組合包
python tools/build_cjk_display_staging.py \
  --mapping localization/cjk_mapping.json \
  --bank-package scratch_test/formal_cjk_fusion_10x10_v22_spell_names/cjk-bank-set.json \
  --spin-package scratch_test/spin_gff_import_title_newline_v4_glossary/gff-text-replacements.json \
  --gpl-package scratch_test/gpl_full_v10_name_records/gpl-dialogue-patch.json \
  --ebox-line-gap 2 --menu-line-gap 2 --dialogue-option-pitch 11 --view-ui \
  --cursor-hotkeys --smart-cursor \
  --output scratch_test/cjk_display_staging_vNN_xxx
```

- 建好後，把 v86r6 的 `SAVE01～08.SAV` 與 `DARKRUN.GFF` 複製進去，讓使用者可以讀進度。
  存檔名稱另存在別的檔，所以讀檔清單上的名字會跟遊戲內不同，但 SAVE01 本身是同一份。
- 只要對話封包改版，舊存檔記住的觸發器位址就可能失效（re_99）。
- **全域字串 GSTR 會存進存檔**：
  - 字串表每格 42 bytes，依序是 GSTR[1] What do you say?、[2] END、[3] CLOSE、[4] What do you do?……
  - 讀舊存檔時，英文標題會被還原回來。
  - 複製存檔之後，要執行 `python tools/patch_save_gstr.py <組合包>/GAME/DARKSUN <對話封包 json>`：
    - 它會把 MAS-99 設定的 GSTR[1][4][5][6][7] 裡還是英文的改成中文。
    - 原檔備份為 `*.orig`。
    - 新開的遊戲不受影響。
- `tests/`：247 項全過，指令是 `python -m pytest tests -q`。

### 0.3 下一輪：程式內字串翻譯——已知事實與限制

**A. 字串從哪裡來**

1. **「WHAT DO YOU SAY?」這類選單標題不在 EXE 裡，已在 v91 處理**：
   - 它們是 GPLDATA 的 `GSTR[1]`（553 個選單）、`GSTR[4]`（12 個），另有 19 個內嵌標題。
   - 繪製程式與修補方式見 0.1 的 v91 條目。
   - 這個做法可以沿用到其他走 `339E:016D` 的畫面：先找到 push 字串指標的那一段，換成 tag redirect，
     讓 FONT 核心解碼到 name-slot。限制是每次繪製最多 10 個相異中文字。
2. **EXE 的畫面字串都在 DGROUP 裡**：
   - DGROUP 在檔案 `0x48960`，執行期段為 `4B7A`。
   - 用「以 NUL 結尾、主要是英文字母」的條件篩選，約有 570 條，內容包括：
     - 遊戲選單（`GAME MENU`、`RETURN TO GAME`、`MUSIC ON`）
     - 戰鬥（`END TURN`、`GUARD`）
     - 背包錯誤訊息（`Too heavy a load to carry`）
     - 狀態（`Stunned`、`Dead`）
     - 法術效果（`Hasted`）
     - 商店（`NO DEAL!`、`SOLD!`）
     - 升級（`CHOOSE A SPELL,`）
     - 法術／靈能名稱（約 150 條）
   - 不含 GUI 錯誤訊息，這部分約 700 bytes，在 `38D7～3B97`。
   - 篩選程式：用 regex `(?<=\x00)[\x20-\x7e]{4,}(?=\x00)` 掃描 DGROUP，再排除檔名、錯誤訊息等。
   - `localization_manifest.json` 裡有 656 筆 `exe_*` 單元，都還沒翻，但混了大量雜訊，
     例如 `X?VCT?VC...`、`Borland C++`。要先清理再開始翻譯。

**B. 技術限制（開工前先想清楚）**

1. **位址換算**：檔案位移 = `0x5400` + (執行期段 − `0x824`) × 16 + 偏移。
   - 例：`339E:016D` → `0x30D0D`；`4B7A:0000` → `0x48960`。
   - 舊文件（re_94）用的 `0xD640` 是錯的。
2. **空間**：一個中文字編碼成 `^xy`，佔 3 bytes。字串在 DGROUP 裡長度固定，原地通常放不下，
   例如 `GAME MENU` 是 9 bytes，「遊戲選單」要 12 bytes。
   - 程式碼用立即值 `push 2403h` 之類引用字串，所以可以把字串搬到別處，再改這些立即值。
   - 問題是 DGROUP 沒有現成的空地：re_56 已證明 DGROUP 尾端不能用。
   - 可能的來源：`38D7～3B97` 這段 GUI 錯誤訊息，以及 `1FA5～1FDD` 的除錯字串。
     但必須先證明這些字串沒有其他引用、改掉不影響功能，才能拿來用。
3. **大多數 UI 繪製路徑不會解碼 Base94**：
   - 主線的常駐 resolver 只掛在 EBOX（對話框），還有 MENU 的行距修補。
   - 最通用的 formatter 是 `339E:016D`（`%C%s%d…`）：
     - `%s` 迴圈在 `339E:02E8`，檔案 `0x30BA0+0x2EB`，逐字呼叫 `11A4:59C1` 畫字。
     - v34／v35 曾經在這個迴圈加解碼，結果畫面空白或當機（re_52、re_53）。
       `build_cjk_display_staging.py` 目前會拒絕這兩個實驗旗標。
     - 這條路徑的前進量是固定的 `寬度('H')+1`，大約 7px（re_63）。10px 寬的中文字會重疊 3px。
   - 物品懸停列、右鍵資訊卡已經實測，都不會解碼（re_101 §2）。
   - 所以翻譯每一條字串之前，都要先確認它走哪條繪製路徑；也可以考慮設計一個安全的通用解碼點。
     這是下一輪的核心問題。
4. **可用的字元碼已經用完**：
   - name-slot 暫借了 10 個碼：`` " # & < > \ ~ ` _ | ``。
   - 材質字首用了 6 個碼：`* @ [ ] { }`。
   - 這 16 個字元只要出現在任何畫面文字裡，就會被畫成中文字形。re_101 §7 的「貝」就是這樣來的：
     `<` 被畫成了殘留的中文字。
   - 所以翻譯後的字串不能含這些字元。看到英文裡夾著莫名的中文字，先查它原本是不是其中之一。
5. **修補 overlay 區**：必須用 `plan_name_slot_consumers.verify_overlay_relocations` 檢查，
   並確認沒碰到 MZ 重定位。`view_ui_layer.apply_view_ui_exe_patches` 是現成的範例。
6. **會被引擎比對的字串不能翻**：
   - `END`、`CLOSE`、`DEBUG`、玩家打字比對的關鍵字、`string compare` 的對象（re_99）。
   - DGROUP 的 `CLOSE`（`1F11`）、`DEBUG`（`1F17`）就是其中之一。

**C. 建議的起手式**

1. 請使用者提供想先處理的畫面截圖或字串（使用者說「有發現一些地方還有其他字串」）。
2. 對每一條字串：
   - 找出引用它的程式碼（搜尋 `push <DGROUP偏移>` 等立即值）。
   - 判斷它走哪條繪製路徑。
   - 評估「原地放得下嗎？」、「路徑會解碼嗎？」。
3. 如果大量字串都走 `339E:016D`，就研究在 formatter 加一個**窄範圍**的 Base94 解碼：
   - 先讀 re_52、re_53、re_63，了解當年失敗的原因。
   - 同時處理 7px 固定前進量的問題。
4. 譯名以 `docs/名詞權威對照表.md` 為準。法術、靈能名稱在對照表裡大多已經有智冠手冊的定名。

### 0.4 其他待辦

1. **避頭點**：換行偶爾會讓「，」「。」出現在行首。
2. **已知風險（目前沒有症狀）**：常駐字型快取 `2E86:545A～5533` 和 name-slot trampoline
   `2E86:5414`，都在計時器 ISR 的私有堆疊 `53B6～55A6` 裡。若出現隨機花字或當機，從這裡查。
3. **名詞**：Psionicist 維持「靈能師」（使用者 2026-09-24 決定），Thief 用「小偷」。

### 0.5 操作注意（本輪學到的）

- **DOSBox-X-AI**：
  - 一律用 PowerShell `Start-Process` 啟動（`-WorkingDirectory` 指到組合包根目錄）。
  - 重開之前，要等 9876 埠釋放。否則新執行個體的 bridge 綁定失敗，會整個停用，
    這時只能再重開一次。
  - 關掉使用者可能正在玩的執行個體之前，要先問。
- **滑鼠座標**：`move_mouse_absolute` 的 x 要用擷取畫面上的 x 乘 2（擷取寬 640，遊戲內容在左半），
  y 不變。
- **快捷鍵**：主選單按 `L` → `Enter` 讀檔。`i` 開背包，`v` 開 VIEW CHARACTER，`1～4` 切換角色。
- **記憶體**：讀之前先 `pause_execution`；讀完記得 `continue_execution`。
- **組合包目錄被佔用**：DOSBox 開著組合包時，那個目錄刪不掉。重建時請換一個新的輸出目錄名。
- **Python 腳本**：寫在 Bash heredoc 裡時，`\x..` 會被轉成真的控制字元。請把腳本寫進暫存目錄的檔案再執行。
- **Unicorn 模擬測試**：同一位址改寫程式碼之後，Unicorn 會沿用舊的翻譯快取。每個 stub 要放在不同位址。

### 0.6 相關文件

| 主題 | 文件 |
|---|---|
| 對話全量編譯、GPL 池、withheld | `docs/re/re_99_*` |
| 背包／VIEW CHARACTER 併入主線 | `docs/re/re_100_v87_view_ui_merge.md` |
| 材質字首、固定字元碼、天生攻擊括號 | `docs/re/re_101_v88_material_words.md` |
| 職業顏色、行距、位址換算更正 | `docs/re/re_102_v89_class_colour_and_view_rows.md` |
| 選單標題、漏抽片段、EXE 字串、FONT 核心 entry、overlay 段號查法 | `docs/re/re_103_v90_v106_menu_titles_and_exe_strings.md` |
| 遊標模式、熱鍵分派、左鍵分派、移動指令、智慧遊標 | `docs/re/re_104_cursor_mode_hotkeys_investigation.md` |
| 選單換頁／疊影 | `docs/re/re_96`～`re_98` |
| `%s` 迴圈解碼失敗紀錄 | `docs/re/re_52`、`re_53`、`re_63` |

---


## 一、重大歷史成就與當前進度總覽

> ⚠️ 以下統計是 **2026-09-21 的歷史快照**，已過時。2026-09-23 實際狀態：
> `dialogue_units.json` 對話單元 **13,295 / 13,295（100%）** 已翻譯；
> `localization_manifest.json` 全遊戲總清單 **13,845 / 14,529** 已翻譯（未譯 684 筆，多為非對話類）。
> 瓶頸已不在翻譯，而在「把翻譯編進 EXE」（見第 0.4 節）。

本專案致力於將經典 CRPG **《浩劫殘陽：破碎大地》(Dark Sun: Shattered Lands)** 進行全文本高品質繁體中文在地化（嚴格依循臺灣智冠官方譯本手冊「珍288」與 AD&D 2nd Edition 經典規則）。

在本輪對話中，連續大批次完封了 **GPL-141 至 GPL-150** 等全部 10 個腳本區塊（本輪累計新譯 **735 筆**對話單元），連續突破各項歷史紀錄：

1. **全遊戲文本總量正式逼近 66%**：
   * **全清單總單元 (`TOTAL ALL`)**：**`9,577 / 14,529`（`65.92%`）**，已達 9,577 筆！
2. **對話單元正式突破 9,000 筆大關（67.9%）**：
   * **對話單元 (`dialogue`)**：**`9,027 / 13,295`（`67.90%`）**，已達 9,027 筆，全遊戲未譯對話已降至 4,268 筆！
3. **腳本連續無斷點大貫通（150 個腳本 100% 零死角）**：
   * **`GPL-1` 至 `GPL-150` 全部 150 個腳本 100% 完封，無任何一筆遺漏**（含 GPL-81、GPL-84 全面清盤補全，GPL-98、GPL-113 無對話純邏輯腳本，MAS-99 全域 UI 提詞，共 148 個實體劇情對話腳本全勝）！
4. **全書英文單詞翻譯量達 68.1%**：
   * **英文單詞 (`Words`)**：**`82,037 / 120,514`（`68.07%`）**，正式突破 82,000 詞大關！
5. **遊戲實機出現次數突破 72.4% 大關**：
   * **實機呼叫 (`Occurrences`)**：**`13,778 / 19,026`（`72.42%`）**，正式達到 13,778 次！
6. **動態 CJK 繁中字庫管線**：
   * 收錄字符 **`2,779 字`**（分佈於 11 個 Bank），容量餘裕達 8,835，`inventory` 與 `compile-catalog` 100% 驗證通過，0 錯誤。
7. **權威名詞對照表**：
   * [`docs/名詞權威對照表.md`](file:///d:/git/Dark%20Sun%20Series/docs/%E5%90%8D%E8%A9%9E%E6%AC%8A%E5%A8%81%E5%B0%8D%E7%85%A7%E8%A1%A8.md) 定版至 **v4.7**，收錄 **757 條**審定專有名詞（增補提奧菲爾、卡夏）。

---

## 二、重要系統環境與注意事項（⚠️ 必讀）

1. **背景常駐任務警告**：
   * 終端機中有一項長期執行的橋接注入程序：`python scratch_test/run_bridge_injection.py`。
   * **⚠️ 絕對不要終止、中斷或 kill 此程序**，請保持其在背景靜默運行。
2. **作業系統與環境**：
   * 作業系統：Windows (PowerShell)。
   * Python 環境：根目錄下直接可用 `python`。
   * 檔案編碼：所有 JSON / Python 檔案使用 `utf-8`，CSV 檔案使用 `utf-8-sig`。
3. **使用者推進風格**：
   * 使用者明確指示：**「可以一次多翻一點 / 一次堆翻一點」**。
   * 請維持大批次（通常為 100～150 筆左右，或 2~4 個中小型 GPL 腳本）連續推進，不要拆碎成過小的單一腳本請求確認。

---

## 三、四大核心檔案同步與空白規範

每次翻譯新腳本時，必須**同時、嚴格同步更新**以下 4 個主目錄檔案：

| 檔案路徑 | 格式 | 說明 |
| :--- | :--- | :--- |
| `localization/catalog/dialogue_units.json` | JSON (utf-8) | 對話單元主庫（含 summary 計數更新） |
| `localization/catalog/dialogue_units.csv` | CSV (utf-8-sig) | 對話單元表格庫 |
| `localization/catalog/localization_manifest.json` | JSON (utf-8) | 全遊戲在地化總清單（含 summary 計數更新） |
| `localization/catalog/localization_manifest.csv` | CSV (utf-8-sig) | 全遊戲在地化總清單表格 |

### ⚠️ 空白對齊鐵律 (Whitespace Alignment Rule)
在《浩劫殘陽》遊戲引擎中，字串開頭與結尾的空格有嚴格的語法或 UI 選項排版意義：
- 選項開頭通常有 2 個空格（`L2:T0`），如 `"  Yes, I agree."` -> `"  是的，我同意。"`。
- 句子拼接前半段通常有結尾空格（`L0:T1`），如 `"I saw him "` -> `"我看見了他 "`。
- 句子拼接後半段通常有開頭空格（`L1:T0`），如 `" in the city."` -> `" 在城鎮裡。"`。
- **所有翻譯字串必須在寫入前經由腳本驗證 `leading_spaces` 與 `trailing_spaces`，必須與原始英文字串完全一致！**

---

## 四、接續推進目標（下一輪重開直接執行）

~~從原版一次重編全部對話翻譯進 EXE~~：已完成（v86r6，re_99）。
~~合併屬性（VIEW CHARACTER）與物品中文化~~：已完成（v87～v89，re_100～re_102）。

**下一個目標：翻譯寫在程式裡的字串（選單標題、EXE 畫面字串）**，已知事實、限制與起手式見第 0.3 節。
