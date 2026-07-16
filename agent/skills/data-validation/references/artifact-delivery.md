# Artifact 交付

必要起始 state：`confirmed`。

1. 呼叫 `gen_validation_rules(workflow_id)`。
2. 呼叫 `gen_readme(workflow_id)`。
3. 依每條已確認的 row rule 撰寫 pure Pandas function body，組成
   `row_impl_code_json` 後呼叫 `gen_data_validation`。不可直接執行或貼入使用者提供的
   SQL/Python 原文。
4. 為每一條 col rule 與 row rule 準備至少一組 concrete `pass_cases` 與 `fail_cases`，組成
   `row_test_code_json` 後呼叫 `gen_test_data_validation`。
5. 將回傳內容寫入：

   ```text
   artifacts/{workflow_id}/validation_rules.json
   artifacts/{workflow_id}/README.md
   artifacts/{workflow_id}/data_validation.py
   artifacts/{workflow_id}/test_data_validation.py
   ```

6. 讀回四個檔案並確認內容與 generator 回傳一致。
7. 在 artifact 目錄執行 `pytest test_data_validation.py`。不可略過失敗；修正 generator input
   或 rules 後重跑。產生的測試應涵蓋每條 rule 的 pass/fail case 與空 DataFrame shortcut，
   不需要 execution-failure test。
8. 使用上述 workspace-relative paths 呼叫 `complete_validation(...)`。
9. 回報 workflow ID、四個路徑、pytest 結果與規則總數。

四個檔案全數寫入、讀回且 pytest 通過前不可宣稱完成。
