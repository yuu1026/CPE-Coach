# CPE 十題 QLoRA 試訓

目的：訓練「依程式與實測證據提供分級提示」，不把完整解答當作 assistant 回覆。原始模型權重不改寫，輸出為 LoRA adapter。

## 題目來源與內容

本批選自常見 CPE 一顆星 49 題選集：10055、10071、10783、11332、10931、272、10035、10038、10041、10812。官方清單頁抓取逾時，星等對照來源為 https://yuihuang.com/cpe-level-1-49/ （該頁連回 CPE 官方清單）。每題題意核對 UVa/Online Judge 原始 PDF，連結保存在 data/problems.json。

摘要、C++ 範例、錯誤變體、測資與教學回覆由本專案重新撰寫，沒有抄錄第三方題解或整篇官方題目。題名與題號保留原來源；不要將本資料宣稱為官方授權題庫或官方 AC 解答。

## 資料組成

- 每題一個正確參考程式、三個不同錯誤類型，共 40 個程式版本。
- 每個版本由本地 Docker judge 實際編譯與測試。正確版必須全部通過；錯誤版必須至少一筆 WA，不能只因環境失敗而標成錯誤。
- 訓練：10 題 ×（正確版＋兩種錯誤）× 三層提示 = 90 筆。
- 評估：10 題 × 保留的第三種錯誤 × 三層提示 = 30 筆。
- 本輪訓練前後 loss 評估使用其中第 1 層的 10 筆；其餘可後續評估。
- 評估題目與訓練相同，只保留不同錯誤類型。這不是未見題目的泛化測試；未來需要另取題目做獨立測試。
- 提示是初稿、尚未經教師獨立審查。編譯判題驗證的是錯誤標籤，不等於教學品質已獲認證。

## 重建資料與重新訓練

先停止模型服務釋放 GPU；網站可保留。於 cpe-ai 環境、專案根目錄執行：

```text
python -m pip install -r training/requirements.txt
python training/build_data.py
python training/train_qlora.py --epochs 1
```

build_data 需要 Docker 指令可用、引擎運作及 cpe-judge:local 映像。若找不到 docker，將 Docker 的 resources/bin 加入此程序 PATH，或重開終端機。train_qlora 只讀本地模型及資料，不會下載另一份模型。

預設輸出 training/runs/cpe10-v1；若已存在會拒絕覆寫。再次實驗請使用不同路徑，例如 `--output training/runs/cpe10-v2`。smoke 測試可用 `--smoke --output training/runs/smoke`，不等於正式訓練。

設定：NF4＋double quant、BF16 計算、rank 8、q_proj/v_proj、microbatch 1、梯度累積 4、學習率 1e-4、gradient checkpointing、單次一個 epoch、種子 42。只計算 assistant 回覆與結束 token 的 loss；system 與學生程式 labels 設為 -100。不會靜默裁切過長資料。

這是小樣本教學行為試訓，不是讓模型「完全學會十題」。loss 下降不等於程式診斷率或答案洩漏率改善。

## 訓練後比較與網站使用

```text
python training/compare_outputs.py
python manage.py seed_cpe10
```

compare_outputs 保存三個保留錯誤案例與三個訓練中正確案例的 base/adapter 對照；正確案例已見過，不能拿來宣稱泛化。人工查看是否找對錯、是否多餘除錯、是否洩漏整題解法。

在 PowerShell 啟動微調模型：

```powershell
cd C:\Users\tt\Documents\Codex\2026-10-26\new-chat\outputs\cpe-coach
$env:HF_MODEL_PATH = 'C:\Users\tt\models\Qwen3-4B-Instruct-2507'
$env:HF_ADAPTER_PATH = "$PWD\training\runs\cpe10-v1"
$env:HF_SERVE_MODEL_NAME = 'Qwen3-4B-CPE10-v1'
& 'C:\Users\tt\miniconda3\envs\cpe-ai\python.exe' local_model_server.py
```

另一個 PowerShell 啟動網站時設定 `OLLAMA_MODEL=Qwen3-4B-CPE10-v1`，其餘網址及 context 維持原值。也可參考根目錄「啟動模型-CPE十題.ps1」與「啟動網站-CPE十題.ps1」。移除 HF_ADAPTER_PATH 並恢復模型名稱，即可回到原始模型。網站讀取 adapter 時無須重新訓練。

新增的十題均使用自編測資，不是原題官方範例；題目摘要與測資設定可在網站資料庫另行擴充。seed_cpe10 只新增，不覆寫既有資料。
