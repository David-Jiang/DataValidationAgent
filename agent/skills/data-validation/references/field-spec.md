# Field Spec 草擬

必要起始 state：`dataset_ready`。

1. 草擬前呼叫 `get_field_spec(workflow_id)`。此工具會回傳具權威性的 JSON Schema，
   並將 workflow 移至 `drafting_spec`。
2. 根據上游 schema、使用者提供的樣本、領域文件與討論建立草稿。
3. 只有上游 metadata 直接提供的事實可使用 `source: "upstream_schema"`；使用者提供或
   確認的驗證要求使用 `source: "discussed_with_user"`。
4. 將未解決的假設標示為 `confidence: "medium"` 或 `"low"`。
5. 只詢問缺少的驗證語意：nullability、string 唯一性、無效值 token、空字串、列舉值、
   pattern、數值範圍與 datetime 邊界或格式。
6. 每個 field 都必須符合該資料型別的規格。`unique` 只適用於 string field。
7. 除非使用者另有指定，初始無效值 token 使用
   `["NULL", "null", "NA", "None", "none"]`。
8. 完整草稿準備完成後，呼叫 `submit_field_spec(workflow_id, field_spec_json)`。

若使用者在提交或確認後修改任何規則，編輯前先呼叫 `get_field_spec(workflow_id)`。此動作會
使舊確認失效，並將 workflow 移回 `drafting_spec`。之後重新提交完整、更新後的正式版 spec。

完成條件：`submit_field_spec` 成功，且 workflow 進入 `awaiting_confirmation`。
