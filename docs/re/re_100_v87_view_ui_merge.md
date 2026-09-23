# re_100：v87 把背包／VIEW CHARACTER 中文化併入主線

> 日期：2026-09-23
> 前置：`re_99`（v86r6）、`HANDOFF_NEXT_SESSION_2026-09-18.md`（v75）、`re_94`／`re_95`
> 產出：`scratch_test/cjk_display_staging_v87_view_ui`（離線驗證完成；實機初測通過，見 §4.1）

## 1. 結論

v75 那條舊 build 鏈（v33 → v55 → … → v75，每版以上一版的 staging 目錄為 parent）
不再需要逐層重跑。實測它對 v33 的差異只有三塊，而且都能直接接在主線後面：

| 部分 | v33 → v75 的實際差異 | 與 v86r6 的關係 |
|---|---|---|
| `DSUN.EXE` | 42 段、547 bytes | 原始位元組全是原版內容，與 v86r6 的 32 段修補**零重疊**；不碰 MZ／overlay 重定位 |
| `RESOURCE.GFF` | 只有 FONT-100（附加 7 個 slot + name-slot 解碼器） | v86r6 的 FONT-100 與 v33 **完全相同**（8,401 bytes，同雜湊）；其他 chunk（SPIN／WIND）互不相干 |
| `GPLDATA.GFF` | 只有 NAME-1（321 筆物品名稱） | v86r6 沒有 NAME-1；對話 chunk 不受影響 |

v58b 雖然改過 WIND-11500，但後來的版本已撤回，v75 最終的 RESOURCE 只剩 FONT-100。
v62 的材質字首修補在 v63 起就不在鏈上（re_84 擱置），這次同樣不啟用。

## 2. 做法

### 2.1 `tools/view_ui_layer.py`（新）

- `VIEW_UI_EXE_PATCHES`：v33 → v75 的完整 EXE 差異表，每筆標註來源版本與用途（redirect
  的 tag 直接從 stub 內的 `B8 xx FF` 解出核對）。套用前逐段比對原始位元組，並檢查 MZ
  重定位、overlay 重定位、修補範圍外零變動。
- `build_view_ui_font()`：在主線 FONT-100 後附加 7 個 10x10 slot（剛好結束在 `0x239B`），
  再接上以主線 mapping 組譯的解碼器。

`build_cjk_display_staging.py` 新增 `--view-ui` 開關，一條指令建完。

### 2.2 解碼器（`cjk_name_slot_cache.asm`／`plan_name_slot_consumers.py`）

- **bank 數**：檔名表改為依 `bank_count` 產生（`C0`～`C15`）。主線傳入 12。這點很重要：
  一般 NAME 路徑（物品名稱）的字 ID 會落在 bank 6～11，舊的 6-bank 解碼器會把它們顯示成「?」。
- **字 ID**：原本寫死在 asm 的 v57 字 ID（性別／種族／陣營／職業／材質）改由
  `localization/catalog/fixed_ui_labels.csv` 經主線 mapping 產生 `name_slot_ui_text.inc`。
  沒傳 `ui_text_ids` 時仍用 asm 內的 v57 舊表，舊 builder 的輸出逐位元組不變（有測試）。
- 以 v57 mapping 加 v75 用字產生的解碼器，與 v75 FONT 內的解碼器逐位元組相同，證明產生器正確。
- `verify_overlay_relocations` 移到 `plan_name_slot_consumers.py`（避免
  `build_cjk_display_staging` → … → `build_name_slot_candidate_from_v33` 的循環匯入），
  `build_view_character_candidate` 仍會轉出這個名稱，舊 builder 不用改。

### 2.3 字元與用字

- 新增 `localization/catalog/fixed_ui_labels.csv`（44 筆固定 UI 字串），並作為 inventory 的第二個
  來源。mapping 只多了一個字：「俠」（ID 3002，bank 11 索引 186），其餘 ID 不變。
- Thief 改為「小偷」（re_95 §2.1 當時只因缺「偷」而暫緩，主線 mapping 已有此字）。
- 其他用字與 v75 相同。

### 2.4 NAME-1 與封包

- `compile_gff_name_records.py` 疊在對話封包上時，要允許 `GFFI-7`（MAS 索引）變動，並繼承
  前一層的 `units`／`withheld`／`abi_constraint`。

## 3. 重建指令

```bash
# 0) mapping（已更新；新增 UI 字串時才需要重跑）
python tools/cjk_localization_pipeline.py inventory \
  --catalog localization/catalog/localization_manifest.csv \
  --catalog localization/catalog/fixed_ui_labels.csv

# 1) bank（bank 0～10 與 v20 逐位元組相同，bank 11 多一個字）
python tools/cjk_localization_pipeline.py build-banks --mapping localization/cjk_mapping.json \
  --output scratch_test/formal_cjk_fusion_10x10_v21_fixed_ui --font Fonts/Fusion_Pixel_10px.ttf \
  --font-size 10 --pixel-width 10 --height 10 --advance 10 --threshold 64 --fit-mode pixel-aligned

# 2) 對話封包（GPLDATA 與 v4 逐位元組相同）
python tools/compile_gpl_dialogue_patch.py \
  --unit-id-file scratch_test/all_translated_unit_ids.txt --output scratch_test/gpl_full_from_pristine_v5

# 3) 疊上 NAME-1
python tools/compile_gff_name_records.py \
  --prior-package scratch_test/gpl_full_from_pristine_v5/gpl-dialogue-patch.json \
  --output scratch_test/gpl_full_v5_name_records

# 4) 組合包
python tools/build_cjk_display_staging.py \
  --mapping localization/cjk_mapping.json \
  --bank-package scratch_test/formal_cjk_fusion_10x10_v21_fixed_ui/cjk-bank-set.json \
  --spin-package scratch_test/spin_gff_import_title_newline_v3_current/gff-text-replacements.json \
  --gpl-package scratch_test/gpl_full_v5_name_records/gpl-dialogue-patch.json \
  --ebox-line-gap 2 --menu-line-gap 2 --dialogue-option-pitch 11 --view-ui \
  --output scratch_test/cjk_display_staging_v87_view_ui
```

v87 雜湊：`DSUN.EXE` `fd0bc1a6…`、`RESOURCE.GFF` `4abb2efc…`、`GPLDATA.GFF` `36182162…`。
FONT-100 共 11,924 bytes（比 v75 多 32 bytes，都是 bank 檔名）。建置後已把 v86r6 的
`SAVE01～08.SAV` 與 `DARKRUN.GFF` 複製進去；對話腳本與 v86r6 相同，存檔的觸發器位址不受影響。

## 4. 驗證

- v87 對 v86r6：EXE 只在 42 段內不同；RESOURCE 只有 FONT-100 不同，且前 8,401 bytes 相同；
  GPLDATA 只有 NAME-1 不同；bank 只有 `C11` 不同。
- transport code（`" # & < > \ ~ \` _ |`）會被解碼器永久改寫 FONT 偏移表。已重查：所有譯文只有
  佔位字 `<active_character_name>` 含這些字元，它不會編進 GPL；23 筆 withheld 英文也沒有。
- 測試：`tests/` 199 項全過。修掉 09-18 以來的 19 個 errors 與 1 個 failure，原因都是測試過時
  （`label_ids` 在 v67 從 4 個擴成 8 個、asm 變長後寫死的位址、v66 性別改回短 span、
  「螳螂戰士」），並新增 `tests/test_view_ui_layer.py`。

### 4.1 實機（DOSBox-X-AI，讀 SAVE01）

- VIEW CHARACTER：GERAKIS「混亂善良／男性 半巨人／角鬥士」、K'RATCHEK「絕對中立／女性
  螳螂戰士／戰士/德魯伊/靈能師」、CILLA「絕對中立／女性 精靈／保護者/德魯伊/小偷」；
  能力值、生命／靈能／防禦標籤都是中文，沒有「?」或疊字。
- 背包：右側能力值與武器名稱（棍棒、反刺）為中文；底部懸停「BONE 反刺」、右鍵資訊卡
  「Bone／反刺／1D8-1」正常。材質字首仍是英文（未啟用，re_84）。
- 滑鼠座標：`move_mouse_absolute` 的 x 要用擷取畫面上的 x 乘 2（擷取 640 寬，遊戲內容在左半）。

## 5. 待辦

1. 使用者自行遊玩確認：對話沒有退化、其他物品與角色。
2. 已知風險沒變：常駐 trampoline `2E86:5414` 與字型快取 `545A～5533` 都在計時器 ISR 的私有堆疊
   （`53B6～55A6`）裡；堆疊要先吃掉快取才會碰到 trampoline。
3. 材質字首已在 v88 解決（re_101）；多職業第三段洋紅色（re_94 §6）仍擱置。
