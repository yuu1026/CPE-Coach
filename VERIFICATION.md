# 驗證紀錄

本次以 Python 3.14.6、Django 6.1.2、HTTPX 0.28.1 執行。

- `manage.py check`：無問題。
- `manage.py test coach`：7 項通過，使用獨立測試 SQLite。
- 測試包括：登入限制、提交與防重送、本人紀錄存取、HTML 跳脫、模型失敗仍保存程式、無效輸入、超出 context 預算拒絕、模擬 live HTTP 回覆、頁面伺服器端呈現。
- 本機 migrate 與 seed_problems 另做啟動資料驗證；交付壓縮檔不含運行資料庫或帳號。

未做真實 Ollama／Pi gateway 呼叫、GPU 微調、學生程式執行、瀏覽器視覺與互動驗證、多人壓力測試。通過伺服器測試不代表模型品質或完整部署驗收。
