# Artifact 交付

必要起始 state：`confirmed`。

1. 詢問使用者是否需要 mock data。若需要但未指定筆數，使用 `row_count=100`；若使用者提供
   正整數，則依指定數量產生。
2. 一律呼叫 `gen_validation_suite(workflow_id)`。
3. 使用者需要 mock data 時，呼叫 `gen_mock_data(workflow_id, row_count)`。
4. 將回傳內容寫入使用者 workspace，且必須使用以下路徑：

   ```text
   artifacts/{workflow_id}/<table_name>_validation_suite.json
   artifacts/{workflow_id}/<table_name>_mock.csv
   ```

   必要時建立 workflow 目錄。不要另外寫入 field-spec artifact。
5. 讀回每個檔案，確認檔案存在且內容與產生器回傳內容一致。
6. 使用 workspace 相對路徑呼叫
   `complete_validation(workflow_id, suite_path, mock_path)`。沒有產生 mock data 時省略
   `mock_path`。
7. 回報 workflow ID、所有交付路徑、已呼叫的 MCP 工具，以及剩餘的低信心規則。

必要 suite 寫入並驗證完成前，不可宣稱完成。MCP Server 只保存 workflow state 與
已確認的 spec，不保存 artifact 檔案。
