# Artifact 交付與 pytest repair loop

必要起始 state：`confirmed`。

1. 呼叫 `gen_validation_rules(workflow_id)`。
2. 呼叫 `gen_readme(workflow_id)`。
3. 依每條已確認的 row rule 撰寫 pure Pandas function body，組成
   `row_impl_code_json` 後呼叫一次 `gen_data_validation`。不可直接執行或貼入使用者提供的
   SQL/Python 原文；成功後 Server 會凍結回傳內容的 SHA-256。
4. 為每條 col/row rule 準備 concrete `pass_cases` 與 `fail_cases`，組成
   `row_test_code_json` 後呼叫 `gen_test_data_validation`。
5. 將回傳內容寫入並讀回確認完全一致：

   ```text
   artifacts/{workflow_id}/validation_rules.json
   artifacts/{workflow_id}/README.md
   artifacts/{workflow_id}/data_validation.py
   artifacts/{workflow_id}/test_data_validation.py
   ```

6. 計算實際檔案的 `data_validation_sha256` 與 `test_data_validation_sha256`。production hash 必須
   與 `get_validation_state` 的 frozen artifact hash 相同。
7. 使用使用者 repo 的真實 Python/test runner 執行 generated test；若使用者要求，也一併執行
   原有 test suite。例如 `uv run pytest -q {generated_test_path} tests`。不可在另一個不相容的
   Python 環境假裝驗證。
8. 每次執行後都呼叫：

   ```text
   record_pytest_result(
     workflow_id,
     data_validation_sha256,
     test_data_validation_sha256,
     return_code,
     pytest_command,
     pytest_output
   )
   ```

9. 若 pytest 失敗，只可修改 `test_data_validation.py` 的環境相容性、imports、fixtures 或測試
   表達方式，再計算新的 test hash、重跑並記錄。不可：
   - 修改或重新產生不同的 `data_validation.py`。
   - 刪除任何 confirmed rule 的 pass/fail coverage。
   - 移除 assertions，或使用 skip/xfail 規避失敗。
   - 把 production implementation bug 改寫成「預期行為」。
10. 連續五次失敗後 MCP 會進入 `blocked`。此時停止自動修復、顯示最後證據並要求人工判斷；
    明確決定繼續後才呼叫 `resume_validation`。
11. pytest 通過後，讀回兩個 Python 檔並重新計算 hashes，再使用四個固定 paths 與通過時的
    `data_validation_sha256`、`test_data_validation_sha256` 呼叫 `complete_validation(...)`。
12. 回報 workflow ID、四個路徑、pytest command/result、attempt count 與規則總數。

四個檔案全數寫入、讀回，最後一次 pytest 成功證據與 production/test hashes 完全相符前，
不可宣稱完成。這是一個由 Agent 執行、MCP state 與 hash gate 管控的 bounded loop。
