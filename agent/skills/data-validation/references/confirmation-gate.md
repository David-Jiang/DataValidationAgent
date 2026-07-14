# 人工確認關卡

必要起始 state：`awaiting_confirmation`。

以完整 Markdown 表格顯示實際提交的完整 spec。不可要求使用者檢閱原始 JSON，也不可
省略 null 或空值。

1. 顯示包含 `workflow_id` 與 `table_name` 的 metadata 表格。
2. 每個 field 顯示一列共通規則：`name`、`dtype`、`nullable`、
   `invalid_value_tokens`、`confidence`、`source`。
3. 顯示各資料型別專屬表格：
   - string：`unique`、`allow_empty_string`、`enum_values`、`pattern`
   - int/float：`min_value`、`max_value`
   - datetime：`datetime_after`、`datetime_before`、`expected_datetime_format`
   - boolean：不需要額外表格
4. 使用 `—`、`[]` 或其他沒有歧義的值，明確顯示 null、空陣列與未設定值。
5. 列出所有中／低信心假設與剩餘風險。
6. 要求使用者確認顯示的完整 spec；簡單明確地回覆 `確認` 即可。
7. 只有收到該回覆後，才可呼叫 `confirm_field_spec(workflow_id)`。

不可將沉默、部分意見、問題或無關討論視為確認。任何規則修改都會使確認失效，
並且必須回到 Field Spec 草擬階段。

完成條件：`confirm_field_spec` 成功，且 workflow 進入 `confirmed`。
