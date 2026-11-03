# Gemma 3 4B IT 切換紀錄

目前模型後端預設為 Google `google/gemma-3-4b-it`，本地 API 名稱為 `gemma-3-4b-it`。網站仍使用既有 49 題題庫、SQLite 學習紀錄與 Docker 判題。

## 實際驗證

- 官方權重下載完成，使用 Gemma3ForCausalLM 與 NF4，只載入文字部分。
- RTX 5060 實際載入並生成繁體中文回覆；短對話測試的 PyTorch 配置記憶體峰值約 2.84GiB。此數字不是長對話、整體 GPU 或微調記憶體需求。
- 使用網站的 build_messages 與 generate_hint，透過 localhost API 完成兩輪連續教學回覆。
- `/healthz` 顯示 ready，模型名稱為 gemma-3-4b-it；網站登入頁回傳 HTTP 200。
- 原 90 筆訓練資料皆通過 Gemma 原生模板的 assistant-only prefix 檢查，最長 643 tokens；此項只有編碼檢查，沒有進行微調。
- 網站自動化測試涵蓋模型路徑、舊 Adapter 拒絕、文字權重映射與不完整權重中止，詳見 coach/tests.py。

可核對 [推論與連線測試結果](verification/gemma3-inference.json)，亦可在模型環境執行 `python tools/check_gemma.py` 重跑 GPU 測試。這些是載入與連線驗證，不是 CPE 診斷正確率、教學成效或 49 題模型評測。

## 模型與資料清理

原機的 Qwen3-4B-Instruct-2507 基礎權重、該模型的 Hugging Face 專屬快取及 cpe10-v1 舊 Adapter 已移除；舊本地壓縮包中的 Adapter 也已移除，保留其原始碼。歷史訓練資料與文字報告保留，並清楚標示為 Qwen 歷史實驗，不是 Gemma 的成績。

GitHub 不包含 Gemma 權重、登入 Token、使用者資料庫或本地服務日誌。其他電腦仍需自行同意 Google 模型條款、下載模型並初始化網站；參考 [接入與啟動說明](../接入已下載模型.md)。

目前使用未微調的 Gemma IT 模型。舊 Qwen Adapter 不可直接轉用；新的訓練預設輸出目錄為 training/runs/gemma3-cpe10-v1，只有重新訓練並評估後才可啟用。
