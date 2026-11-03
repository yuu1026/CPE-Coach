# CPE Coach

以本地大型語言模型與實際 C++ 判題證據，提供逐步提示的 CPE 學習輔導網站。目標是協助學生理解與修正自己的程式，而不是直接產生整題答案。

## 專案流程圖

![CPE Coach 學習流程](docs/diagrams/learning-flow.svg)

[查看完整流程圖](docs/FLOWCHARTS.md)：包含使用者流程、系統架構、測試與詢問分流、連續對話，以及十題 QLoRA 訓練。

## 功能

- 49 題 CPE 一星選集，下拉選題與個人完成進度；每題包含自寫題意摘要、自編輸入與預期輸出。
- 程式可留白，從題意、手算與小問題開始引導。
- 連續對話：回覆助理時不必離開解題頁，不同練習各自保存。
- 「送出訊息」與「執行測試」分開，避免每次對話都重新編譯。
- Docker 隔離的 C++17 編譯、測資執行與預期輸出比對。
- 程式與全部測資一致時，詢問可沿用同一段對話的測試結果並標記來源。
- 三欄深色工作區、離線語法編輯器、響應式頁籤與失敗測資優先展開。
- Google Gemma 3 4B IT 的純文字 NF4 推論，以及 49 題教學 QLoRA 微調與評估流程。

## 快速啟動：不需要 GPU 的示範模式

建議 Python 3.12。先將 repository clone 到電腦並進入其根目錄，在 PowerShell 執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_cpe49
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

開啟 [本地網站](http://127.0.0.1:8000)，以剛建立的帳號登入。沒有預設帳號或密碼。預設 `HINT_MODE=demo`，回傳固定示範提示，不會分析實際程式。`seed_cpe49` 只新增題目，不覆寫既有資料；原本十題的提交紀錄及完成標記會保留。`seed_cpe10` 保留為原十題匯入指令；`seed_problems` 是早期三題自編範例，目前不出現在 CPE 題庫。

既有專案升級：在目前 Python 環境依序執行 `python manage.py migrate`、`python manage.py seed_cpe49`，並執行 `docker build -t cpe-judge:local ./judge` 更新判題映像，之後重新啟動網站。參考 [49 題題庫說明](docs/CPE49.md)。新增題目不代表重新訓練模型，原機已完成 Gemma 的兩個 49 題微調實驗候選，尚未設為預設；舊 Qwen Adapter 不相容，十題結果另保留為歷史實驗。

Linux/macOS 的虛擬環境 Python 路徑為 `.venv/bin/python`；模型訓練與 Windows GPU 相依套件另行配置。

## 啟用 C++ 判題

先安裝並啟動 Docker Desktop 的 Linux containers，確認 `docker version` 同時顯示 Client 和 Server，再於專案根目錄執行：

```powershell
docker build -t cpe-judge:local ./judge
```

網站會用容器執行程式，不會直接在宿主機執行學生 C++。容器停用網路、限制 CPU/記憶體/程序數/輸出量與執行時間。沒有 Docker 或引擎未就緒時會顯示環境狀態，不會退回宿主機執行。

詳細限制及測資比較方式見 [編譯與測資功能](編譯與測資功能.md)。這是本機專題用隔離機制，不是經過對抗性驗證的公開線上 judge。

## 接入 Google Gemma 3 4B IT 本地模型

目前已完成原機的模型替換與連線實測，見 [Gemma 切換紀錄](docs/GEMMA-MIGRATION.md)。模型權重不包含在 GitHub 中。

請先至 [Google 官方模型頁](https://huggingface.co/google/gemma-3-4b-it) 登入 Hugging Face 並同意模型條款，再在自己的終端機登入，Token 不要放進原始碼。使用具 CUDA 支援的獨立 Python 環境。以下命令需在已安裝相容 CUDA PyTorch 的環境中執行；不要在網站示範環境中任意混裝不同版 PyTorch。

```powershell
python -m pip install -r requirements.txt -r requirements-model.txt
python -m pip install huggingface_hub
hf auth login
hf download google/gemma-3-4b-it --local-dir ./models/gemma-3-4b-it
$env:HF_MODEL_PATH = "$PWD\models\gemma-3-4b-it"
Remove-Item Env:HF_ADAPTER_PATH -ErrorAction SilentlyContinue
$env:HF_USE_BASE_MODEL = '1'
$env:HF_SERVE_MODEL_NAME = 'gemma-3-4b-it'
python local_model_server.py
```

另一個 PowerShell，在同一個環境與專案根目錄啟動網站：

```powershell
$env:HINT_MODE = 'live'
$env:Model_URL = 'http://127.0.0.1:11436'
$env:Model_Name = 'gemma-3-4b-it'
$env:CONTEXT_TOKENS = '4096'
python manage.py runserver 127.0.0.1:8000
```

`Model_URL` 與 `Model_Name` 分別設定模型服務網址與模型名稱；實際呼叫的是本專案的 Hugging Face 推論服務，不需要另外安裝 Ollama。服務使用 `Gemma3ForCausalLM`，只載入文字模型，以 4-bit NF4 推論；不載入視覺編碼器。使用 Gemma 原生對話模板與實際 tokenizer 檢查上下文，不裁切本輪程式碼。

相依套件需配合 GPU、驅動、PyTorch/CUDA 與 Python 版本。先前 Qwen 曾於 RTX 5060 8GB 試訓；Gemma 的推論與微調需分別實測，不能沿用舊模型的記憶體數字。參考 [模型接入說明](接入已下載模型.md)，目前啟動入口已改用專案相對路徑。設定讀取環境變數，**不會自動載入 `.env`**。

## 49 題 Gemma 教學微調實驗

已實際完成兩個候選版本，均以全部 49 題建立的 539 筆對話訓練一個 epoch、135 次更新，包含分級找錯提示、通過測資的回饋、空白起步與連續對話。另有 147 筆同題不同錯誤程式的評估對話；loss 使用其中第一層的 49 筆。

| 候選 | Learning rate | 平均 assistant loss 前 → 後 | 部署決定 |
|---|---:|---:|---|
| v1 | 0.00005 | 7.8525 → 2.1955 | 保留為實驗，不設為預設 |
| v2 | 0.00001 | 7.8525 → 3.4718 | 保留為實驗，不設為預設 |

回覆雖變短，但六個情境的抽查仍有定位不準、只重述測試結果或誤述題意的問題，因此網站預設維持 Gemma 基礎 IT 模型。loss 不等於診斷正確率；這些題目都出現在訓練中，也不是未見題目的泛化測試。PyTorch 配置記憶體峰值約 5.30GiB，不等於整體 GPU 使用量。

[資料與重建流程](training/CPE49.md) · [兩版比較與決定](training/reports/cpe49-selection.json) · [v1 報告](training/reports/gemma3-cpe49-v1/training_report.json) · [v2 報告](training/reports/gemma3-cpe49-v2/training_report.json)

原機保留兩版 Adapter，可用「啟動模型-CPE49實驗.ps1」與「啟動網站-CPE49實驗.ps1」指定 -Version v1 或 v2，比較前請先停止目前模型與網站，避免佔用相同 GPU/連接埠。GitHub 不含權重，其他電腦需重新訓練。一般啟動入口不會自動啟用未通過回覆檢查的實驗權重；也可加 -BaseModel 明確使用基準模型。

## 歷史十題微調實驗（Qwen，非目前 Gemma 的成績）

以下為先前 Qwen 的實驗，不能視為 Gemma 的訓練或效能證據。目前 Gemma 的 49 題實驗結果另見上節，網站預設仍維持基礎模型。舊實驗的基礎模型為 [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)。以自行撰寫、經 Docker 驗證的程式與錯誤變體，建立 90 筆訓練對話、30 筆同題不同錯誤類型的評估對話。

- 訓練一個 epoch、23 次參數更新，rank 8 QLoRA。
- 原機 PyTorch 最高配置 GPU 記憶體約 5.53 GiB。
- 10 筆保留案例的平均 assistant loss：7.28 → 2.37。
- 評估題目仍是訓練見過的十題；loss 不代表診斷正確率或學習成效。
- 回覆抽查仍有提示過於籠統的案例。此為試驗模型，不宣稱已完整學會十題。

[訓練流程](training/README.md) · [實驗說明與限制](training/本輪訓練結果.md) · [訓練報告](training/reports/cpe10-v1/training_report.json) · [回覆對照](training/reports/cpe10-v1/generation_comparison.json)

模型與 adapter 權重不放進 Git。新的訓練入口預設 Gemma 的 49 題資料，輸出至 `training/runs/gemma3-cpe49-v1`；必須重新訓練並評估，才能設定 `HF_ADAPTER_PATH` 載入新的 Adapter。舊 Qwen Adapter 無法沿用。原始模型權重不會被覆寫。題目摘要、程式、測資與提示由本專案編寫；原題來源逐題保存在 `training/data/problems.json`，不是官方授權題庫或完整官方題目重刊。

## 專案結構

```text
coach/                 Django 資料模型、流程、判題、權限與測試
config/                網站設定與路由
templates/             題庫與解題工作區
static/                本地編輯器、樣式、對話互動與第三方授權
judge/                 隔離編譯與執行容器
data/                  49 題網站題庫與實際測資驗證報告（不含解答）
tools/                 題庫重建與維護者參考程式驗證工具
training/data/         自編訓練、評估、題目與實測稽核資料
training/reports/      可追溯的實驗結果
training/              資料建立、QLoRA 與回覆比較程式
```

網站架構參考課堂 Django／FastAPI 分層教材，原教材與校內資料庫、金鑰未納入 repository。本專案使用 SQLite，與校內共用資料庫無關。

## 驗證

```powershell
python manage.py check
python manage.py test coach
```

網站測試涵蓋 49 題匯入與模型切換設定，原有測試包括帳號隔離、防重送、連續對話、判題結果沿用與失效、完成標記、空白程式引導、頁面與靜態資產。另通過 JavaScript 語法與 Markdown 注入檢查。新版 UI 尚未完成實際瀏覽器視覺與點擊驗證，見 [UI 更新說明](UI更新說明.md)。

## 資料、授權與部署界線

`.gitignore` 排除虛擬環境、模型、adapter、資料庫、`.env`、本地網站密鑰與壓縮檔。首次啟動會建立本機 `.local-secret`，帳號與紀錄只存在本機 SQLite。分享與提交前仍應確認沒有自行新增的敏感資料。

第三方前端元件使用 MIT 授權，授權檔與固定版本來源保存在 [static/vendor](static/vendor/README.md)。Gemma 基礎模型依 [Google Gemma 條款](https://ai.google.dev/gemma/terms) 使用。Repository 未另行授予本專案原始碼的開源授權。

此版本適合 localhost 開發與課堂展示；`runserver`、本地靜態資產路由與現有 Docker 判題設計不應直接作為公開服務。公開部署需另行規劃正式主機、HTTPS、工作佇列、容量限制、專用沙箱、資料同意與刪除機制。
