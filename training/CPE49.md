# Gemma 3 4B IT：49 題教學微調

以本專案 49 題一星選集的自寫題意、參考程式、錯誤變體與分級教學回覆進行 QLoRA。目的為逐步引導與錯誤修正，不把完整解答當作 assistant 訓練目標。

## 本輪結果與使用方式

兩個候選都已完成 539 筆、一個 epoch、135 次更新。v1 learning rate 0.00005，loss 7.8525→2.1955；v2 learning rate 0.00001，loss 7.8525→3.4718。

六個情境的實際回覆仍出現問題：v1 有錯誤的診斷描述；v2 有只重述輸出差異、沒有定位整數範圍，以及誤述機器人越界規則的案例。兩版都沒有設為網站預設，基礎 Gemma 服務已恢復。這不代表基礎模型沒有問題，而是本次尚未證明微調能可靠改善提示品質。

實驗權重保存在 training/runs/gemma3-cpe49-v1 與 gemma3-cpe49-v2，不推送 GitHub。想在原機比較，先停止目前模型與網站，再分別於兩個已啟用 cpe-ai 的 PowerShell 執行：

```powershell
./啟動模型-CPE49實驗.ps1 -Version v2
```

```powershell
./啟動網站-CPE49實驗.ps1 -Version v2
```

-Version v1 可比較第一版。使用一般啟動腳本加 -BaseModel 可回到基礎模型。比較結果、每例回覆及抽查判讀均保留於 reports/gemma3-cpe49-v1、reports/gemma3-cpe49-v2 與 [版本選擇紀錄](reports/cpe49-selection.json)。沒有產生 deployment_ready.json，故一般啟動入口不會將實驗權重當成正式版本。

## 資料

| 類型 | 訓練對話數 |
|---|---:|
| 已通過測資，避免捏造錯誤 | 147 |
| 每題一個實際失敗程式、三層提示 | 147 |
| 程式空白時的起步引導、三層提示 | 147 |
| 承接學生回答 | 49 |
| 釐清學生的錯誤想法 | 49 |
| 合計 | 539 |

評估另保留每題一個不同的錯誤程式，三層共 147 筆對話。訓練前後 loss 使用其中第一層的 49 筆。題目在訓練中都出現過；這是同題不同錯誤程式的評估，不是未見題目的泛化，也不是 147 個獨立錯誤程式。

共 49 個正確版與 98 個錯誤版，合計 147 個 C++17 程式，均經 Docker 編譯與執行。正確版必須通過全部自編測資，錯誤版必須至少產生一次輸出不符。驗證確認程式標籤，教學回覆仍是專案作者初稿，尚未經教師獨立審查。來源與執行證據保存於 data/cpe49/verified_programs.jsonl。

## 重建

在有 Docker 與 cpe-judge:local 的環境執行：

```powershell
python training/build_cpe49_data.py
```

預設沿用程式、測資與判題政策 SHA-256 相符的紀錄；加 `--recheck` 會重新編譯全部程式。原十題的歷史資料與報告保留，沒有改寫為新模型成績。

## 訓練

停止正在執行的模型服務以釋放 GPU。於已安裝 CUDA PyTorch、requirements-model.txt 及 training/requirements.txt 的環境執行：

```powershell
python training/check_loss.py
python training/train_qlora.py --output training/runs/gemma3-cpe49-v1
python training/compare_outputs.py --adapter training/runs/gemma3-cpe49-v1
```

輸出資料夾若已存在，程式會拒絕覆寫。重跑請提供新的 --output；單步環境測試可加 --smoke，且應使用不同輸出資料夾。

兩版均使用 NF4 double quantization、BF16 計算、rank 8、q_proj/v_proj、batch 1、累積 4、一個 epoch，共 135 次更新；第二版另外指定 --learning-rate 0.00001。只計算最後一輪 assistant 的 loss，之前的 prompt、學生程式、歷史對話均不作訓練標籤。

為符合 8GB GPU，凍結的 embedding/head 使用 BF16；只在有監督目標的位置建立 vocabulary logits。CPU 小型 Gemma 測試已核對，此作法與完整 logits 的 assistant-only causal loss 及所有參數梯度相符。完整對話超長時直接拒絕，不默默裁切程式。

## 評估與未來啟用條件

訓練報告記錄實際更新次數、資料 SHA-256、訓練前後 loss 與 PyTorch 配置記憶體峰值。回覆比較涵蓋三個保留錯誤、一個通過案例、空白起步及承接回答；六個抽樣不能代表整體診斷正確率或答案洩漏率。

只有完整訓練、檢查回覆，且 deployment_ready.json 的權重 SHA-256 與完整訓練紀錄一致時，預設啟動入口才選用 `gemma-3-4b-cpe49-v1`。Git clone 未含本地 Adapter 時仍選用 `gemma-3-4b-it`。模型權重不推送到 GitHub。

啟動方式仍是 `./啟動模型.ps1` 與 `./啟動網站-真實模型.ps1`。兩者均可加 `-BaseModel` 使用未微調模型，方便比較或回復基準版本。結果數據以 [新版訓練報告](reports/gemma3-cpe49-v1/training_report.json)與 [回覆對照](reports/gemma3-cpe49-v1/generation_comparison.json)為準。

## 下一步改進方向

增加每題多種真實且經確認的錯誤案例與教師修訂回饋，降低固定模板比重；另保留未參與調參的題目與程式作最終評估。這次六個案例已用於選擇是否啟用，不能再視為獨立測試。進一步比較應檢查錯誤定位、題意忠實度、是否捏造執行證據、完整答案洩漏及連續引導，而不能只比較 loss 或回覆長度。
