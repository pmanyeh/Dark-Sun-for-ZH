# 《浩劫殘陽》繁中化：下一個 session 交接（2026-09-18，v75 更新版）

## 0. 目前唯一正式可玩 checkpoint（VIEW CHARACTER 這一輪已結束）

```text
scratch_test/cjk_display_staging_v75_view_column_shift2
```

**使用者已明確表示 VIEW CHARACTER 屬性介面的翻譯工作到此為止**
（"屬性介面的翻譯，我覺得就先到這裡"），下一輪要轉往**對話選項**
（見第 0.1 節）。這個 checkpoint 是這整條 VIEW CHARACTER 工作線
（`re_85`～`re_95`，跨多個 session）目前、也是最終的成果。

Parent 是 **v71**（多職業職業名稱修復＋10 插槽字形池，見 `re_94`），
依序疊上 v72（下半部版面間距調整＋兩處名詞對照修正）、v73（第二輪
間距微調）、v74（EXP／靈能欄位 X 座標左移，第一次移太多造成疊字，
已修正）、v75（EXP／靈能欄位再往右微調 4px，使用者確認滿意）——
完整記錄見 `re_95` 第 1.1～1.3 節。已實機驗證
GERAKIS／K'RATCHEK／CERMAK／CILLA 四位角色，VIEW CHARACTER 畫面
下半部四行間距分布均勻、EXP 與靈能欄位跟左側內容間距適中、沒有任何
疊字，種族「螳螂戰士」、職業「保護者」翻譯已修正。啟動方式：
`base.conf` 已是 `autolock=false`；用 DOSBox-X-AI debugger bridge
啟動後，主選單按 **L 再按 Enter** 讀取存檔（比滑鼠點擊可靠），進遊戲
後按 **v** 鍵直接開啟 VIEW CHARACTER 畫面。

`scratch_test/cjk_display_staging_v70_view_layout_reflow`／`v71`／
`v72`／`v73`／`v74` 都已經是**過時 checkpoint**，除非要對照回歸測試，
否則之後都用 v75。

## 0.1 下一階段：對話選項（Dialogue Options）

使用者要求下一輪把重心轉往對話選項的中文化。**這不是全新領域**——
本專案在更早的 session 已經對「對話文字」本身做過大量逆向工程與
中文化（`re_37`／`re_40`／`re_42`／`re_77`／`re_78`／`re_80` 等），
下一輪開始前建議先讀 `re_80`（`DSUN 客體原生 Hires 對話文字
checkpoint`，目前對話文字這條線最新的記錄）搞清楚現況，**不要假設
從零開始**。VIEW CHARACTER 這條線（`re_85`起跳）用的技巧（tag
redirect、FONT-local NAME slot cache、`ds_relative_consumer_redirect_bytes`
等）大部分是同一套底層機制，可以互相參考，但對話選項畫面本身
（多選項選單的排版、逐項高亮、點擊命中區等）是否已經處理過、處理到
什麼程度，需要先讀 `re_80` 跟往前追它引用的文件才能確認，這份交接
文件不重複整理。

**實機測試對話選項的操作方式**（來自專案根目錄 `HotKey_in_Game.txt`）：
跟 NPC 對話、畫面出現多個選項時，直接按數字鍵 **1~5** 就會選擇對應
那一行選項，不用滑鼠點擊——跟 VIEW CHARACTER 這條線「L→Enter 讀檔、
v 鍵開角色頁」是同一種「優先用鍵盤快捷鍵、不要用滑鼠座標猜」的測試
原則，選對話選項時直接套用。`HotKey_in_Game.txt` 裡其他熱鍵（`I`
開背包、`C`/`U` 開施法選單、`Tab` 開遊戲選單等）如果之後要測試其他
畫面也用得到，可以直接查那份檔案，不用重新在遊戲裡試。

## 1. 本輪完成事項（已實機驗證，本文件取代先前 v70 交接版本的第 1.3／
第 3 節）

### 1.1～1.4：陣營／性別種族版面、HP:/PSI: 標籤、單職職業名稱、
v70 下半部版面重排

承接更早的 session，內容不變，詳見 `re_87`／`re_89`／`re_91`／`re_93`
第 1 節。**不需要重新研究這部分**。

### 1.5 多職業職業名稱徹底修復（v71，本輪主線工作，見 `re_94`）

`re_93` 當時把多職業職業名稱亂碼問題評估後保守退回英文顯示。本輪先用
即時反組譯把 `5B7C:2DC1`（VIEW CHARACTER 多職業組字函式）的完整呼叫
結構釘死（雙職／三職路徑都只呼叫**一次** `339E:016D`，事先收集全部
遠指標；解碼順序永遠是「後面欄位先解碼、slot1 最後」），確認根因跟
`re_93` 的假設一致：共用的 `name_buffer` 跟共用的 7 個實體字形插槽會被
後解碼的欄位覆寫。

修法兩塊：

1. `class_slot2_decoded`／`class_slot3_decoded` 各自把解碼結果複製到
   私有緩衝區（`class_slot2_buffer`／`class_slot3_buffer`），不再回傳
   共用的 `name_buffer` 指標。
2. 一次性旗標 `class_skip_reset`，讓非群組第一個解碼的職業欄位跳過
   插槽池重置、繼續往前一個欄位的插槽上累加——**從角色紀錄本身現場
   判斷「我是不是這組第一個」，不依賴任何呼叫歷史**（`re_93` 第二輪
   嘗試疑似用的是「所有職業 tag 一律跳過重置」，對無關欄位的插槽池
   殘留完全沒有防呆）。

過程中額外挖到一個**修復前就存在的既有 bug**：`decode_start` 的
`malformed_triple`（插槽池滿了或 Base94 資料損毀時的錯誤處理路徑）只用
`inc si` 跳過 1 個 byte，沒跳過完整的 3-byte triple，導致溢位時垃圾
資料位元組會被當成字面字元複製進緩衝區。已修正成跟 `emit_slot`／
`glyph_error` 一致的 `add si, 3`。

修完這兩塊後，K'RATCHEK／CILLA（各 8 個相異字形，超過原本 7 個插槽）
只剩 1 個字優雅降級成 `?`（不再亂碼）。使用者確認後，本輪**同一會期
內**接著把插槽池從 7 個擴充到 10 個，徹底消掉這個 `?`：

- 关键是先用即時除錯核對出正確的定址換算公式：
  `[font_pointer]` 相對位移 = `OFFSET label` − `FONT_RUNTIME_BASE_OFFSET`
  （`0x0004`，`plan_name_slot_consumers.py` 裡原本就有的常數，這次
  實測核對出它就是 `[font_pointer]` 的 offset 部分）。`re_93` 當時用的
  「加上 `0x239B`」方向、數值都是錯的（那個常數是給另一件事用的，見
  `re_94` 第 5.1 節）。
- 新增 `class_extra_slots`（我們自己 payload 裡的 306 bytes 儲存區，
  供插槽 8-10 用）、3 個新 transport code 字元（反引號／底線／直線，
  **刻意不選 `/`**——`/` 是多職業畫面本來就會用的字面分隔符，拿來當
  transport code 會讓分隔符忽而變成亂碼字）。
- `copy_staging_to_slot` 依插槽編號 `>7` 分岔，換算到跟內建插槽同一套
  `[font_pointer]` 相對位移空間後，其餘邏輯共用不變。

四位角色（含插槽池擴充後）實機全部驗證通過，`?` 完全消失：

```text
GERAKIS:   角鬥士
CERMAK:    保育師/角鬥士
K'RATCHEK: 戰士/德魯伊/靈能師
CILLA:     保育師/德魯伊/盜賊
```

完整技術細節、定址換算推導過程、實機驗證記錄全部在 `re_94`。

**注意（不是 bug，不用重新調查）**：K'RATCHEK 的「德魯伊」會顯示紅色、
「靈能師」會顯示洋紅色，第二/第三個職業常常不是白色——這是《浩劫殘陽》
**原始、未修改遊戲本身就有的職業配色**，已經用即時追蹤排除跟字形內容/
插槽編號有關，並在姊妹倉庫 `dsun-hires-text-poc` 的
`v7/README.md`／`HANDOFF_2026-09-11_v7_accepted_v8_pending.md` 兩份
獨立文件（他們直接擷取未修改遊戲的繪圖指令得到的實機資料）裡找到
「實測德魯伊是紅色」的交叉驗證。中文化版本忠實呈現了這個原生配色，
不需要也不應該修正。細節見 `re_94` 第 6 節。

建置腳本：`tools/build_view_class_multi_candidate.py`（v71，parent 為
v68b）。

## 2. 本次發現的即時除錯／組語技巧（累加自 v70 交接版本，新增第 6-7 條）

1. **VIEW CHARACTER 進入方式**：遊戲畫面按 `v` 鍵直接開 VIEW CHARACTER。
2. **7 個下半部欄位的座標都是簡單的 `push dword Y:X` 立即值**，不是
   tag-redirect。找法見 v70 交接版本第 2.2 條（斷點在 `5FB0:1907`
   重新定錨）。
3. **FONT 自己的 payload 起點換算（v71 已用實測修正）**：組譯器看到的
   `OFFSET label`（`cjk_name_slot_cache.asm` 裡）是 **CS 相對**，但
   `glyph_loader`／`copy_staging_to_slot` 用的 `first_slot_offset` 等
   常數是 **`[font_pointer]` 相對**。這兩個位移空間換算公式（本輪
   用即時除錯核對出來，不是理論推導）：
   `[font_pointer] 相對位移 = OFFSET label − FONT_RUNTIME_BASE_OFFSET(0x0004)`。
   `re_93` 當時用「`OFFSET label + 0x239B`（`FONT_CORE_PAYLOAD_OFFSET`）」
   是**方向跟數值都錯的**——`0x239B` 是給 `0x0714` trampoline「跳進我們
   自己程式碼」用的常數，不是給「定址我們自己資料」用的。以後要在 FONT
   payload 裡新增資料且需要 `[font_pointer]` 相對定址時，套用上面這個
   已驗證的公式。
4. **`0x0714`（FONT segment 內固定偏移）** 是遊戲原生的 trampoline，
   `les bx,[font_pointer]; add bx,0x239B; retf`，把 `[font_pointer]`
   相對位移轉成 CS 相對後跳進我們自己的 payload。
5. **DOSBox-X-AI debugger bridge 的 `step_over`／`step_into` 對
   `int 3F` overlay-loader trampoline 不可靠**，做法見 v70 交接版本
   第 2.5 條。
6. **（v71 新增）想知道「CS 相對」跟「`[font_pointer]` 相對」換算常數
   時，直接斷點在自己 payload 內部讀 `CS` 暫存器最可靠**：這次直接在
   `class_slot2_label_entry` 等處斷點，讀出 `CS` 就等於 `[font_pointer]`
   的 segment 本身，再讀 `DS:[0xA378]` 拿到 offset 部分，兩者核對出
   `FONT_RUNTIME_BASE_OFFSET` 就是這個 offset，比從原始碼/常數名稱
   猜測換算方向可靠很多。
7. **（v71 新增）DOSBox-X-AI debugger bridge 偶爾會出現「回應 id 持續
   錯位」（`DOSBOX_PROTOCOL_ERROR: response id N does not match request
   id N+1`）的狀況，重試/换工具都無法恢復**：這不是 `known-bugs.md`
   記錄過的遊戲側 bug，是這次 session 才遇到的 bridge 連線問題。唯一
   有效的解法是直接砍掉 `dosbox-x.exe` 行程、重新啟動——新的連線會
   正常。

## 3. 目前刻意保留、尚未解決的問題

**多職業職業名稱第三段顯示洋紅色**（`re_94` 第 6 節、`re_95` 第 4
節）：`?`／亂碼問題已完全解決，但 K'RATCHEK／CILLA 的第三個職業名稱
（`靈能師`／`盜賊`）會顯示成寫死的洋紅色 `(255,0,255)`，不是原本該有
的黃色——已確認**不是**跟字形內容或插槽編號有關（用即時記憶體比對
排除過），已追到遊戲引擎自己一個沒有文件記錄、狀態相依的顏色/畫筆
管理函式（`339E:016D` 呼叫 `11A4:5956`），但黑箱單步追蹤已經到瓶頸
（同一組參數開始重複、數值失去意義），沒找到精確觸發條件或修法。
使用者已同意先擱置。**下次要碰這個問題，先讀 `re_94` 第 6 節，裡面有
完整的排查記錄（含哪些理論已經排除），不要從頭猜。**

**Thief 職業譯名「小偷」需要新增字形**（`re_95` 第 2.1 節）：使用者
的名詞對照要求 Thief 譯成「小偷」，但「偷」這個字完全不在
`cjk-mapping-v57.json`（1330 筆已知字元）裡，需要跑一次字形新增流程
（不是單純改資料表）。CILLA 的第三個職業目前維持「盜賊」，等使用者
決定要不要另外排一次會期處理。

**DAM:/EXP: 標籤本身沒有翻譯**（`re_88` 第 6.7 節已定位字串位置但消費
端未確認）——這是使用者自己上一輪要求暫緩的（"DAM、EXP的標籤也先
不用翻譯了"），不是遺漏，除非使用者主動要求恢復這項工作，否則不用
主動處理。

多職業職業名稱的**亂碼／`?`降級**問題（`re_93` 記錄、`re_94` 修復）
已經完全解決，不再是待解決項目——只剩上面「第三段洋紅色」這個純顯示
顏色的獨立問題。

## 4. 使用者標準偏好（跨 session 持續有效）

- 回覆一律用**正體中文**。
- 啟動 DOSBox-X 測試版本時**不要自動鎖滑鼠**（`autolock=false`）。
- 主選單用 **L 鍵→Enter** 讀取存檔，比滑鼠點擊可靠。
- 遇到 Dark Sun EXE 逆向工程卡關時，檢查姊妹倉庫
  `d:\git\dsun-hires-text-poc` 有沒有相關線索——但注意該倉庫目前活躍的
  工作內容（VGA page-flip／EBOX 邊界追蹤，見其
  `v9/delegation/result-067-*.md`）跟本專案 VIEW CHARACTER 這條線
  **不相關**，只是同一批底層逆向技巧的來源，不用去讀它最新的調查
  細節。
- 懷疑 Dark Sun 崩潰/顯示異常前，先查 `vendor/opends` 的
  `known-bugs.md`／`engine-quirks.md`，別急著怪自己這輪的改動。
- 專有名詞翻譯統一維護在單一 glossary 檔案（本專案的 localization
  catalog／mapping 體系），不要散落各處重複定義。

## 5. 下一個 session 建議閱讀順序

```text
docs/re/HANDOFF_NEXT_SESSION_2026-09-18.md   本文件
```

**若要開始對話選項工作**（下一輪主線，見第 0.1 節）：先讀
`re_80`（對話文字目前最新 checkpoint），不要從零開始重新調查。

**若要回頭處理 VIEW CHARACTER 遺留的兩個已知、已記錄問題**（不是
必要，使用者已同意這輪先不做）：

- 「第三段洋紅色」顯示問題：先讀 `re_94` 第 6 節（完整排查記錄），
  不要從頭猜。
- Thief「小偷」缺字形問題：先讀 `re_95` 第 2.1 節。
- 其他 VIEW CHARACTER 相關工作（DAM:/EXP: 標籤翻譯等）：先讀
  `re_88`（欄位/呼叫點總覽）以及 `re_89`（tag-redirect 在 VIEW 自己
  overlay 裡的標準做法）。

不需要重新研究：陣營/性別/種族定位與翻譯（`re_85`～`re_87`，已定案）、
HP:/PSI: 標籤機制（`re_89`，已定案）、單職職業名稱翻譯（`re_91`，
已定案）、多職業職業名稱亂碼/`?`問題（`re_93` 記錄問題、`re_94` 完整
修復，已定案）、v75 版面座標本身（`re_95` 第 1 節已含完整位移表）、
種族/職業名詞對照修正（`re_95` 第 2 節，已定案，Thief 除外）——整條
VIEW CHARACTER 工作線（`re_85`～`re_95`）**這輪已由使用者確認結束**，
除非使用者主動要求，否則不用主動回頭處理。

## 6. 本輪（v72~v75）新增／修改檔案清單

```text
tools/cjk_name_slot_cache.asm                （HP/PSI 標籤 X/Y 座標、
                                               class_preserver／race_7
                                               字元 ID 修正）
tools/build_view_layout_adjust_candidate.py   （v72，parent 為 v71）
tools/build_view_layout_adjust2_candidate.py  （v73，parent 為 v72）
tools/build_view_column_shift_candidate.py    （v74，parent 為 v73）
tools/build_view_column_shift2_candidate.py   （v75，parent 為 v74，
                                                目前基準，VIEW CHARACTER
                                                最終版本）
docs/re/re_95_v72_layout_spacing_and_terminology.md   （v72~v75 完整記錄）
```

v71 新增的檔案（`tools/build_view_class_multi_candidate.py`、
`docs/re/re_94_*.md`）維持不變，是 v72~v75 的 parent 鏈源頭，仍是理解
多職業職業名稱機制的必讀文件。

早於 v71 的 build 腳本（`build_view_class_names_candidate.py` 等 v68
系列、`build_view_class_level_combined_candidate.py` v69）維持原樣，
是歷史記錄，不用再看。
