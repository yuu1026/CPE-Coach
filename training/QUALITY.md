# 回答品質實驗 quality-v3

本輪以繁體中文、C++17、具體診斷與多輪對話為目標。資料由 GPT/Codex 助理新撰的對話種子與回覆規則，結合專案既有的題意、錯誤變體及 Docker 執行證據組成。沒有呼叫另一個 GPT API，也尚未經獨立教師複核。

## 資料與隔離

- 訓練：347 筆，35 個 UVa 題目，加上通用 C++ 教學情境。
- 驗證：9 筆，另保留 7 題與 2 個獨立情境，用於候選版本選擇。
- 最終測試：12 筆，另保留 7 題、3 個對話情境及其中 2 題的完整程式生成。
- 三個 split 的 UVa 題號不重疊，完整輸入雜湊不重疊；通用程式概念仍會重疊，且基礎模型及過去實驗可能已見過這些題目。
- 完整參考解答不會放入模型輸入。要求完整解答的訓練樣本才有完整程式作 assistant 目標。
- 程式與測資的 SHA-256 必須符合既有 Docker 紀錄。這證明自編測資的執行標籤，不證明教學回覆的每句推理都正確。
- 每筆 provenance 與分割雜湊見 [manifest](data/quality-v3/manifest.json)。

## 訓練與比較

先停止模型服務，避免爭用 GPU。在專案根目錄的 cpe-ai 環境執行：

```powershell
python training/build_quality_data.py
python training/train_qlora.py --data-dir training/data/quality-v3 --output training/runs/gemma3-quality-v3 --max-length 2560 --epochs 1 --learning-rate 0.00001 --warmup-ratio 0.1 --eval-all-levels
python training/evaluate_quality.py --adapter training/runs/gemma3-quality-v3 --split eval --output training/reports/gemma3-quality-v3/dev.json
```

資料最長 2342 tokens，沒有裁切對話或程式。訓練使用 NF4 QLoRA、rank 8、q_proj/v_proj、batch 1、累積 4、87 次更新、10% warmup 後 cosine learning-rate decay；僅最後一輪 assistant 計算 loss。輸出資料夾存在時會拒絕覆寫。

候選版本在驗證集選定後，才執行最終測試：

```powershell
python training/evaluate_quality.py --adapter training/runs/gemma3-quality-v3 --split test --output training/reports/gemma3-quality-v3/test.json
```

比較時載入同一份基礎權重，分別停用與啟用 adapter，以相同解碼設定生成。評估原始文字，不經網站的繁體轉換、答案查表、重試與程式格式化。程式生成交給既有 Docker 判題，絕不在 Windows 主機執行。

## 品質判讀

自動規則檢查繁體字、C++、輸出完整性、題目關鍵概念、是否亂稱已測試，以及未要求時是否給整題程式。這些只是啟發式檢查，不是語意正確率。每項原始回覆仍需逐一閱讀。

自評以 0–5 分記錄直接性、正確性與教學幫助：0 無法回答，1 主要內容錯誤，2 模糊或有明顯缺陷，3 大致相關但不足，4 正確且可採取下一步，5 正確、清楚、具體且連貫。重大錯誤包括錯誤演算法、捏造執行結果、未承接問題與未要求即洩漏完整程式。自評由 GPT/Codex 作成時必須標明，不冒充獨立人工評閱。

候選至少須在驗證及最終測試各通過 90% 自動檢查、每例自評至少 4 分、沒有重大錯誤，且平均自評比基準提高至少 0.25 分。這是本專案的選用條件，不代表模型在其他題目都能達到高品質；不符合就保留原部署。

```powershell
python training/quality_gate.py --dev training/reports/gemma3-quality-v3/dev.json --test training/reports/gemma3-quality-v3/test.json --review training/reports/gemma3-quality-v3/review.json --output training/reports/gemma3-quality-v3/decision.json
```

工具只產生決策報告，不會自行改動目前模型或寫入啟用標記。權重保持本地，GitHub 只保存資料、程式與實際報告。

教師資料的擴充規格見 [TEACHER_PROMPT.md](TEACHER_PROMPT.md)。

## 第一候選的實際結果

quality-v3 已完成 87 次更新，驗證 loss 由 4.9454 降至 4.3048，但逐筆回覆出現轉向、字串索引、排序與型別提升的錯誤。9 筆驗證的啟發式檢查，原始模型通過 6 筆、候選通過 5 筆；這不是語意正確率。逐筆 GPT/Codex 自評平均為 1.33/5 與 0.89/5，尚未經獨立教師複核。因此拒絕啟用，也沒有使用最終測試集為這個失敗候選補分。

[實際訓練報告](reports/gemma3-quality-v3/training_report.json) · [原始回覆](reports/gemma3-quality-v3/dev.json) · [逐例自評](reports/gemma3-quality-v3/dev_review.json) · [決策](reports/gemma3-quality-v3/decision.json)

## 修正後的資料與候選

在閱讀上述驗證失敗後，修正「程式空白一律當作起步引導」的模式判斷，將一般概念問答分開；另外提供綁定題目摘要 SHA-256 的題意重點，避免把轉向、中心對稱與格式規則說反。這是驗證集導向的改進，不能再把驗證集稱為完全未見的測試。

quality-v4 資料有 353 筆訓練、9 筆驗證、14 筆最終測試。增加六筆具體對照與兩個最終的執行證據一致性案例，並更正四個驗證案例的概念關鍵字；因此不能直接把 v3、v4 的啟發式通過數當成相同指標比較。兩個版本的原始資料與雜湊分別保留。

全層訓練的候選 v4 曾中斷，沒有完整權重或品質結果，不列為成功實驗。接續候選 v5 使用相同 quality-v4 資料，只調整最後八個 decoder 層的 q/k/v/o/gate/up/down，rank 8，共約 350.6 萬可訓練參數；一個 epoch、累積 4、89 次更新、learning rate 0.00003、10% warmup 後 cosine decay，每 10 次更新保存部分 Adapter 檢查點。

```powershell
python training/build_quality_v4_data.py
python training/train_qlora.py --data-dir training/data/quality-v4 --output training/runs/gemma3-quality-v5 --max-length 2560 --epochs 1 --learning-rate 0.00003 --warmup-ratio 0.1 --eval-all-levels --target-modules q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj --last-layers 8 --checkpoint-every 10
python training/evaluate_quality.py --adapter training/runs/gemma3-quality-v5 --data-dir training/data/quality-v4 --split eval --output training/reports/gemma3-quality-v5/dev.json
```

檢查點不是完整訓練成果，不可冒充通過評估的模型。若需從部分權重繼續學習，可加 `--warm-start-adapter training/runs/舊實驗/checkpoints/step-0010` 並提供新的 `--output`；這會重新建立 optimizer 與 epoch 排程，不是逐步精確恢復中斷狀態。

已保存的特定版本 JSONL 才是重現歷史報告的資料。重建工具使用目前提示詞，可能產生新雜湊；請勿覆寫正在訓練或報告引用的資料。`--refresh-test-only` 會先要求訓練與驗證資料逐位元相同，才允許補充尚未執行的最終測試。

完整實驗可使用兩個終端機分別啟動：

```powershell
./啟動品質實驗.ps1 -Service Model -RunName gemma3-quality-v5
```

```powershell
./啟動品質實驗.ps1 -Service Website -RunName gemma3-quality-v5
```

這些是實驗入口；一般啟動入口仍遵循既有部署選擇，不因新檢查點存在就自動啟用。

## 第二個完整候選與提示格式實驗

v5 完成 353 筆訓練、89 次更新，驗證 loss 由 4.8768 降至 3.2012，PyTorch 配置顯存峰值約 5.30 GiB。這項改善沒有轉化成可靠的找錯能力，因此同樣拒絕設為預設。v4 中斷不算完整訓練成果。

| 9 筆開發集，基準／v5 | 自動規則通過 | GPT/Codex 自評平均（0–5） |
|---|---|---|
| 原 JSON 提示 | 3/9、3/9 | 1.00、1.11 |
| 可讀分段提示 | 4/9、3/9 | 1.56、1.56 |

逐筆自評不是獨立教師評分，規則通過也不是語意正確率。可讀提示讓兩者的繁體文字檢查均達 9/9，但仍出現錯改排序、誤判輸出空行與未要求就給整題程式。此結果不支持「已達高品質」的結論。開發集已用於調整，不可冒充盲測；14 筆最終測試尚未執行，避免對已失敗候選反覆挑選成績。

[訓練報告](reports/gemma3-quality-v5/training_report.json) · [JSON 提示原始回覆](reports/gemma3-quality-v5/dev.json) · [可讀提示原始回覆](reports/gemma3-quality-v5/dev-readable.json) · [逐例自評](reports/gemma3-quality-v5/dev-readable_review.json) · [拒絕啟用決策](reports/gemma3-quality-v5/decision.json)

可讀提示的比較指令：

```powershell
python training/evaluate_quality.py --adapter training/runs/gemma3-quality-v5 --data-dir training/data/quality-v4 --split eval --plain-prompts --output training/reports/gemma3-quality-v5/dev-readable.json
```

網站傳給模型的內容改為分段題意、目前程式、執行證據，最後才放最新問題；資料庫仍保留結構化內容供追溯。這是提示傳輸調整，沒有讓失敗的 Adapter 自動上線。

## 可追溯的局部診斷提示

98 個已有 Docker 實測紀錄的單一錯誤變體，可依題目摘要與 C++ token 簽章取得專案撰寫的三級提示。僅容許一般程式空白與註解差異；前處理指令、字串與運算子保持區別。未知程式仍交由模型回答，後續追問也回到連續對話。

畫面明確標示「題庫診斷提示（未呼叫模型）」，並說明未重新執行。這是窄範圍查表，不是模型學會 98 種錯誤，更不能宣稱任意程式的診斷正確率。訓練及模型評估資料均關閉這項查表，以免把答案放進輸入造成虛高成績。

目前資料由 GPT/Codex 編寫的合成種子、模板及專案審核案例組成；本輪沒有呼叫付費 GPT API，也沒有獨立教師複核。擴大資料前應先提供本機 API 金鑰、可用模型 ID 與費用上限，依教師資料規格產生、編譯驗證、交叉評閱及去重；不能只靠增加 epoch 或降低 loss 宣稱品質提升。

## 依使用者原程式回答（提示 v11）

有目前程式時，完整解答請求不再直接回傳題庫參考程式，而由模型在原寫法上處理。空白編輯器要求完整解答時仍可使用有標示來源的參考程式。傳給模型時移除歷史使用者的舊程式片段，保留問答；目前完整程式靠近最新問題，明確要求引用原運算式、保留命名與思路，再說明局部修改。

網站對有程式的模型回答檢查是否引用目前程式片段；泛泛而談或只引用舊版時最多重試一次，再失敗就明確回報，保留使用者程式。這只是引用格式檢查，不是語意分析器，不能保證模型的錯誤定位、程式或說明正確；不會自動修改編輯器，也不會偷偷執行使用者程式。

實際基礎模型的三個局部案例都引用原程式並沿用命名，但整數平均與乘法案例的文字解釋仍有重要錯誤。因此不能把三次成功回傳宣稱為三題回答正確。此次沒有換權重或呼叫 GPT API，歷史資料與評估結果也保持原樣。

[原始實測](reports/code-grounding-v11.json) · [逐例限制與自評](reports/code-grounding-v11-review.json)

```powershell
python training/smoke_code_grounding.py --output training/reports/code-grounding-new-run.json
```

這個小型檢查直接呼叫本地基礎模型並使用網站的提示／一次重試流程，省去 HTTP；不代表整個網站端到端或獨立測試集的正確率。

## 從實際系統失敗繼續修正

Vito 的完整修正版曾因變數作用域錯誤無法編譯。後續 v6／v7 的資料審核、格式修正、抽樣比重、實際微調與拒絕啟用結果，見 [REPAIR.md](REPAIR.md)。v7 的作用域修正已有進步，但乘法與文字解釋仍失敗，所以未替換預設權重。網站提示 v13 另外對模型完整程式做隔離編譯檢查；這道檢查不是模型訓練成果，也不代表測資或演算法正確。

v14 後加入題庫測資驗證，教學版本再補題意與計算工具、分步草稿任務及局部新增顯示。它們是應用支援，不是裸模型能力；完整程式驗證通過也不等於能教懂。實際自我驗證仍判定尚未達到可靠自主教學，見 [TEACHING.md](TEACHING.md) 與[逐例評估](reports/tutoring_assessment_20261116.json)。
