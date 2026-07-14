# Artifact 交付

必要起始 state：`confirmed`。

1. 一律呼叫 `gen_validation_suite(workflow_id)`。
2. 一律呼叫 `gen_mock_data(workflow_id)`。不可詢問使用者是否需要或要求使用者指定筆數。
   Server 會產生全反向資料，基準為 100 筆；規則較多時可超過 100，最多 1000 筆。
3. 一律呼叫 `gen_field_spec_csv(workflow_id)`。
4. 將三個回傳內容寫入使用者 workspace，且必須使用以下路徑：

   ```text
   artifacts/{workflow_id}/<table_name>_validation_suite.json
   artifacts/{workflow_id}/<table_name>_mock.csv
   artifacts/{workflow_id}/<table_name>_field_spec.csv
   ```

   必要時建立 workflow 目錄。
5. 讀回每個檔案，確認檔案存在且內容與產生器回傳內容一致。
6. 使用 workspace 相對路徑呼叫
   `complete_validation(workflow_id, suite_path, mock_path, field_spec_path)`。
7. 回報 workflow ID、所有交付路徑、已呼叫的 MCP 工具，以及剩餘的低信心規則。

三個 artifacts 全部寫入並驗證完成前，不可宣稱完成。MCP Server 只保存 workflow state 與
已確認的 spec，不保存 artifact 檔案。全反向 mock CSV 的每列至少違反一條規則，目的是讓
ETL 後接 validation suite 時能驗證各條規則確實會抓到錯誤資料。
