# Validation Rules 草擬

必要起始 state：`dataset_ready`。

1. 呼叫 `get_field_spec(workflow_id)`，取得權威 field-spec JSON Schema並進入
   `drafting_rules`。
2. 依 upstream schema、樣本、文件與使用者討論完成 field spec。它只負責產生 col rules；
   dtype-specific 條件仍以 schema 支援的 null、unique、invalid token、empty string、enum、
   pattern、numeric range、datetime range/format 為準。
3. 同時詢問跨欄位商業語意。使用者可用自然語言、SQL 或其他方式說明，但 Agent 必須正規化
   為 row rule，不可執行輸入內容。
4. 每條 row rule 必須：
   - 使用唯一且以 `row.` 開頭的 `id`。
   - 具體中文 `desc`。
   - `columns` 至少列出兩個 input schema 中存在的欄位。
   - `examples.pass` 與 `examples.fail` 各至少一筆 `{"name": "...", "sql": "..."}`。
5. `input_schema` 由 field spec 自動縮減為 `name`、`dtype`；不要自行提交額外欄位。
6. 呼叫 `submit_validation_rules(workflow_id, field_spec_json, row_rules_json)`。沒有 row rule 時
   明確傳入 `[]`。

若使用者在提交或確認後修改任何 col/row rule，先再次呼叫 `get_field_spec`，重新提交完整
field spec 與完整 row-rule array。

完成條件：workflow 進入 `awaiting_confirmation`。
