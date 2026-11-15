# 從 Vito 實際失敗建立的修正實驗

來源是 [UVa 10041 系統驗證](reports/live-system-vito-20261116-summary.md)：模型把變數宣告放在分支內，後面卻在外面使用，並錯誤描述整數運算。這次改動同時包含本地 QLoRA 訓練與網站編譯檢查；兩者的效果必須分開判讀。

## 資料與限制

- 五種焦點：Vito 平均數改中位數、Vito 分支作用域、一般分支作用域、整數除法與加法提升、乘法前提升運算元。
- v6 共 96 筆不同訓練對話，其中 80 筆為模板衍生的提示／追問／完整修正／已通過回饋，另外保留 16 筆既有教學對話。
- 28 組錯誤／正確程式對照，正確版通過實際 Docker 測資，錯誤版編譯失敗或答案不符。
- v6 部分完整目標的 Markdown 收尾未獨立換行，雖然程式本身通過驗證，仍屬資料品質缺陷；保留原版並另建 v7 修正，沒有覆寫歷史資料。
- v7 統一完整目標的 C++ 排版與程式區塊，將完整修正範例抽樣三次，共 136 筆訓練記錄，仍只有 96 筆不同對話。不能把抽樣副本當作新增獨立資料。
- v7 的 21 份不同排版後完整程式再次通過 Docker 測資，見[格式修正版程式審核](reports/gemma3-quality-v7/formatted_target_audits.json)。
- 各保留 4 筆開發、4 筆最終測試。題型與 Vito 已見過，主要分開程式命名與案例實例，不是未知題目或獨立學生的盲測。開發集已用於改進，最終測試不能反覆挑分。

資料由 GPT/Codex 與專案程式生成，沒有呼叫付費 GPT API，也沒有獨立教師複核。教師回覆、完整答案查表與題庫診斷查表不放進完整修正的輸入；「已通過」案例則刻意包含使用者已經寫對的程式與真實證據。

## 訓練與比較

同一 Gemma 3 4B IT 基礎模型、NF4 QLoRA、rank 8、batch 1、累積 4、assistant-only loss。v6 只調整最後八層，共 350.6 萬可訓練參數；v7 調整全部文字層的 q/k/v/o/gate/up/down，共 1490.1 萬可訓練參數。兩版都從基礎模型開始，沒有接續失敗 Adapter。

```powershell
python training/build_repair_data.py
python training/build_repair_v7_data.py
python training/audit_repair_v7.py
python training/train_qlora.py --data-dir training/data/quality-v7 --output training/runs/gemma3-quality-v7 --max-length 2560 --epochs 2 --learning-rate 0.0001 --warmup-ratio 0.1 --eval-all-levels --target-modules q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj --checkpoint-every 17
python training/evaluate_quality.py --adapter training/runs/gemma3-quality-v7 --data-dir training/data/quality-v7 --split eval --output training/reports/gemma3-quality-v7/dev.json
```

以上路徑已存在時，建置與訓練會拒絕覆寫；重現時請另建版本及輸出路徑。實際歷史輸入以版本化 JSONL 與 manifest SHA-256 為準。評估原始輸出不使用 OpenCC、題庫參考答案、編譯修復重試或網站格式化；完整程式的通過判定來自 Docker 實測，文字說明仍需逐筆閱讀。自動規則不是語意正確率。

v6 完成 48 次更新，loss 3.2871 → 1.9646；三個完整程式案例由基準 1/3 提升為候選 2/3，但作用域與解釋仍錯誤，原始規則只有 0/4，故拒絕啟用。其[決策](reports/gemma3-quality-v6/decision.json)與[逐例自評](reports/gemma3-quality-v6/dev_review.json)保留。v6 舊報告的分項摘要曾把不適用項算成通過；新版工具已分開適用分母，完整程式數應依 `code_judge` 實際列數判讀，不應沿用那個舊分項數字。

v7 完成 68 次更新，loss 2.9726 → 0.1710，訓練及末次 loss 評估約 309 秒，不含載入與訓練前評估。PyTorch 配置顯存峰值約 5.30 GiB。四個開發案例的原始規則由基準 1/4 提升為候選 2/4；完整程式由 1/3 提升為 2/3，繁體文字檢查由 3/4 提升為 4/4。作用域完整修正與局部提示已正確，但整數除法被說成餘數，乘法案例插入錯誤的 `std::max(left,right)`，使負數測資失敗。因此同樣拒絕啟用，不把低 loss 當作高品質；各 4 筆最終生成測試未執行，原 quality-v4 的 14 筆最終生成測試也未動用。

GPT/Codex 逐例自評平均為基準 1.25/5、v7 2.75/5，並非獨立教師評分。作用域案例的進步不能推廣成所有 CPE 題都已學會。新權重僅保留本地實驗，一般網站恢復使用基礎模型並套用下面的編譯檢查。

[v7 訓練報告](reports/gemma3-quality-v7/training_report.json) · [原始回答與 Docker 結果](reports/gemma3-quality-v7/dev.json) · [逐例自評](reports/gemma3-quality-v7/dev_review.json) · [拒絕啟用決策](reports/gemma3-quality-v7/decision.json)

若要手動比較本地實驗版本，需先停止既有服務，分別使用：

```powershell
./啟動品質實驗.ps1 -Service Model -RunName gemma3-quality-v7
./啟動品質實驗.ps1 -Service Website -RunName gemma3-quality-v7
```

這是未通過選用門檻的實驗版本，不是一般啟動入口的預設。GitHub 不包含 Adapter 權重。

## 網站完整程式的檢查

提示 v13 起先對模型完整解答做隔離編譯檢查。[v13 實測](reports/live-system-vito-v13-20261116.json)發現模型能修到編譯成功，卻退回錯誤的平均數算法，因此 v14 以後再比對題庫測資。只有模型新產生的完整程式會接受這項自動驗證，使用者編輯器內容仍由「執行測試」獨立提交。沒有可用題庫測資時只做編譯，不捏造輸入。

編譯或測資失敗時，將候選程式及真實差異獨立標為資料，最多重試一次；不取代使用者原程式或把候選結果誤當原程式證據。第二次仍失敗就回報失敗。有測資時明示通過幾組，否則明示「只通過編譯、未執行測資」；Docker 不可用時明示尚未驗證。通過測資不驗證文字解釋，也不代表官方AC。

[重播驗證](reports/gemma3-quality-v6/compile_guard_replay.json)使用歷史失敗回答及固定修正候選，實際呼叫 Docker，證明會攔截作用域錯誤並保留使用者程式；這不是新模型的準確率。

```powershell
python training/replay_compile_failure.py
```

只有完整開發／測試與逐例評閱符合 [品質門檻](QUALITY.md)的候選才可考慮部署；loss 下降、成功回傳、通過編譯都不能取代語意與測資驗證。

後續針對「能否真正引導寫程式」的四輪九回合對話與跟隨提示編碼，仍未達可靠教學標準，詳見 [TEACHING.md](TEACHING.md)。
