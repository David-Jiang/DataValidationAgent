# MCP Tool Workflow

可用 MCP tools：

- `get_table_schema(dataset_urn)`：取得上游 table schema。
- `get_field_spec()`：取得 `field_spec` 的權威 JSON Schema。
- `gen_mock_data(field_spec_json, row_count)`：根據已確認的 `field_spec` 產生 CSV mock data。
- `gen_validation_suite(table_name, field_spec_json)`：根據已確認的 `field_spec`
  產生 Great Expectations suite JSON。

必守順序：

1. 建立或修改 `field_spec` 前，必須先呼叫 `get_field_spec()`，並完全遵守其 JSON Schema。
2. 草擬 table-specific rules 前，必須先呼叫 `get_table_schema(dataset_urn)`。
3. 若使用者尚未提供 DataHub dataset URN，先詢問。
4. `field_spec` 是 generation 的唯一依據。
5. 使用者明確確認 final `field_spec` 前，不可呼叫 `gen_mock_data` 或 `gen_validation_suite`。
6. 任何 MCP tool 只要回傳以 `ERROR:` 開頭的內容，必須立即停止後續 workflow。

若 tool 回傳 `ERROR:`，不可繼續呼叫後續 tools、不可草擬或更新 `field_spec`、
不可產生 mock data、不可產生 validation suite。向使用者說明錯誤，要求修正必要輸入或環境，
並等待使用者提供可通過的資訊。

例如 `get_table_schema` 回傳 DataHub 連線錯誤、找不到 dataset，或 dataset URN 不正確時，
必須等待使用者提供正確且可查詢的 DataHub dataset URN，不能自行猜測或繼續草擬。
