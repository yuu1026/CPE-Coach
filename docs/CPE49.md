# CPE 一星 49 題網站題庫

網站題庫由十題擴充至常見的一星 49 題選集。下拉選題、空白程式起步引導、連續對話、分開執行測試與詢問，以及個人完成標記，均可用於新增題目。

## 匯入與升級

先在專案根目錄、已安裝 Django 的 Python 環境執行：

```powershell
python manage.py migrate
python manage.py seed_cpe49
docker build -t cpe-judge:local ./judge
```

重新啟動 Django 並重新整理首頁，即可看到 49 題。匯入可重複執行，只新增缺少的題目，保留既有題目的內容、主鍵、學生提交及完成標記。原本 `seed_cpe10` 仍可使用，但只匯入原十題。

新增資料存於 `data/cpe49.json`，每題包含繁體中文自寫摘要、原題來源、自編輸入與預期輸出，不包含參考解答。題目內容直接來自資料庫，因此無須逐題修改 HTML 或另外註冊路由。

## 來源與範圍

題號清單對照 [CPE 一顆星選集 49 題整理](https://yuihuang.com/cpe-level-1-49/)，該頁連回 [CPE 官方清單](https://cpe.cse.nsysu.edu.tw/environment.php#starList)。本次官方清單頁連線逾時，因此用整理頁核對選集成員；新增題目的輸入、輸出與規則另逐題核對 Online Judge 原題，連結見下表。

本站提供重新撰寫的題意摘要及自行設計的測資，不是官方題庫全文重刊，也不包含官方隱藏測資。每題至少兩組獨立測試輸入；新增的 39 題每題至少三組，一組輸入可包含多個案例。

## 判題差異

- 預設：統一換行，忽略整體結尾空白，其餘逐字比較。
- UVa 490：忽略每行結尾補齊空白，行首與行中空白仍需相符。
- UVa 10221：輸出數值個數須相同，逐個以絕對誤差不超過 0.000001 比較，不接受 NaN/Infinity。
- 自訂測資沿用同題規則。規則由題庫設定，不由學生提交的表單決定。

編譯產物的單檔上限改為 16MiB，避免 STL 模板程式被原本 64KiB 限制誤擋；學生程式執行時仍使用原本 64KiB 單檔限制。請重建 Docker 映像。判題政策版本已更新，舊版結果不會被當成新版測試證據沿用。

## 驗證與模型限制

```powershell
python tools/build_cpe49.py
python tools/validate_cpe49.py
python manage.py test
```

第一個指令可重建網站資料，不改動十題訓練資料。第二個指令在 Docker 編譯維護者自行撰寫的 C++17 參考程式，對照題庫中獨立撰寫的預期輸出，全數成功才寫入 `data/cpe49-validation.json`。參考程式只供維護驗證，不經網站或模型提示輸出給學生。這些測資仍不足以取代正式線上評測。

49 題擴充沒有重新微調模型。專案後續已改用 Google Gemma 3 4B IT 基礎模型；先前 `Qwen3-4B-CPE10-v1` Adapter 只用原十題訓練，無法套用到 Gemma。新增 39 題會透過題意、使用者程式及執行證據交給模型分析，其提示品質需要另行評估；不能宣稱模型已經微調學會全部 49 題。

## 題目清單

| UVa 題號 | 題目 | 原題 |
|---|---|---|
| 100 | The 3n + 1 problem | [Online Judge](https://onlinejudge.org/external/1/100.pdf) |
| 118 | Mutant Flatworld Explorers | [Online Judge](https://onlinejudge.org/external/1/118.pdf) |
| 272 | TEX Quotes | [Online Judge](https://onlinejudge.org/external/2/272.pdf) |
| 299 | Train Swapping | [Online Judge](https://onlinejudge.org/external/2/299.pdf) |
| 490 | Rotating Sentences | [Online Judge](https://onlinejudge.org/external/4/490.pdf) |
| 948 | Fibonaccimal Base | [Online Judge](https://onlinejudge.org/external/9/948.pdf) |
| 10008 | What's Cryptanalysis? | [Online Judge](https://onlinejudge.org/external/100/p10008.pdf) |
| 10019 | Funny Encryption Method | [Online Judge](https://onlinejudge.org/external/100/10019.pdf) |
| 10035 | Primary Arithmetic | [Online Judge](https://onlinejudge.org/external/100/10035.pdf) |
| 10038 | Jolly Jumpers | [Online Judge](https://onlinejudge.org/external/100/10038.pdf) |
| 10041 | Vito's family | [Online Judge](https://onlinejudge.org/external/100/10041.pdf) |
| 10050 | Hartals | [Online Judge](https://onlinejudge.org/external/100/10050.pdf) |
| 10055 | Hashmat the brave warrior | [Online Judge](https://onlinejudge.org/external/100/10055.pdf) |
| 10056 | What is the Probability? | [Online Judge](https://onlinejudge.org/external/100/10056.pdf) |
| 10057 | A mid-summer night's dream | [Online Judge](https://onlinejudge.org/external/100/10057.pdf) |
| 10062 | Tell me the frequencies! | [Online Judge](https://onlinejudge.org/external/100/10062.pdf) |
| 10071 | Back to High School Physics | [Online Judge](https://onlinejudge.org/external/100/10071.pdf) |
| 10093 | An Easy Problem! | [Online Judge](https://onlinejudge.org/external/100/10093.pdf) |
| 10101 | Bangla Numbers | [Online Judge](https://onlinejudge.org/external/101/10101.pdf) |
| 10170 | The Hotel with Infinite Rooms | [Online Judge](https://onlinejudge.org/external/101/10170.pdf) |
| 10189 | Minesweeper | [Online Judge](https://onlinejudge.org/external/101/10189.pdf) |
| 10190 | Divide, But Not Quite Conquer! | [Online Judge](https://onlinejudge.org/external/101/10190.pdf) |
| 10193 | All You Need Is Love | [Online Judge](https://onlinejudge.org/external/101/10193.pdf) |
| 10221 | Satellites | [Online Judge](https://onlinejudge.org/external/102/10221.pdf) |
| 10222 | Decode the Mad man | [Online Judge](https://onlinejudge.org/external/102/10222.pdf) |
| 10226 | Hardwood Species | [Online Judge](https://onlinejudge.org/external/102/10226.pdf) |
| 10235 | Simply Emirp | [Online Judge](https://onlinejudge.org/external/102/10235.pdf) |
| 10242 | Fourth Point!! | [Online Judge](https://onlinejudge.org/external/102/10242.pdf) |
| 10252 | Common Permutation | [Online Judge](https://onlinejudge.org/external/102/10252.pdf) |
| 10268 | 498-bis | [Online Judge](https://onlinejudge.org/external/102/10268.pdf) |
| 10409 | Die Game | [Online Judge](https://onlinejudge.org/external/104/10409.pdf) |
| 10415 | Eb Alto Saxophone Player | [Online Judge](https://onlinejudge.org/external/104/10415.pdf) |
| 10420 | List of Conquests | [Online Judge](https://onlinejudge.org/external/104/10420.pdf) |
| 10642 | Can You Solve It? | [Online Judge](https://onlinejudge.org/external/106/10642.pdf) |
| 10783 | Odd Sum | [Online Judge](https://onlinejudge.org/external/107/10783.pdf) |
| 10812 | Beat the Spread! | [Online Judge](https://onlinejudge.org/external/108/10812.pdf) |
| 10908 | Largest Square | [Online Judge](https://onlinejudge.org/external/109/10908.pdf) |
| 10922 | 2 the 9s | [Online Judge](https://onlinejudge.org/external/109/10922.pdf) |
| 10929 | You can say 11 | [Online Judge](https://onlinejudge.org/external/109/10929.pdf) |
| 10931 | Parity | [Online Judge](https://onlinejudge.org/external/109/10931.pdf) |
| 11005 | Cheapest Base | [Online Judge](https://onlinejudge.org/external/110/11005.pdf) |
| 11063 | B2-Sequence | [Online Judge](https://onlinejudge.org/external/110/11063.pdf) |
| 11150 | Cola | [Online Judge](https://onlinejudge.org/external/111/11150.pdf) |
| 11321 | Sort! Sort!! and Sort!!! | [Online Judge](https://onlinejudge.org/external/113/11321.pdf) |
| 11332 | Summing Digits | [Online Judge](https://onlinejudge.org/external/113/11332.pdf) |
| 11349 | Symmetric Matrix | [Online Judge](https://onlinejudge.org/external/113/11349.pdf) |
| 11417 | GCD | [Online Judge](https://onlinejudge.org/external/114/11417.pdf) |
| 11461 | Square Numbers | [Online Judge](https://onlinejudge.org/external/114/11461.pdf) |
| 12019 | Doom's Day Algorithm | [Online Judge](https://onlinejudge.org/external/120/12019.pdf) |
