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

若 tool 回傳 `ERROR:`，先修正輸入或 `field_spec`，再向使用者說明修正點。
