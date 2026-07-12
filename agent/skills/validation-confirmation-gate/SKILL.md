---
name: validation-confirmation-gate
description: 與使用者 review 完整 field_spec，並在產生 validation artifact 前強制取得明確確認。使用於 field_spec 可送審時，或先前已確認的規則被修改後。
---

# Field Spec 確認 Gate

1. 將完整 final `field_spec` 整理成人類可讀的 Markdown tables；不可要求使用者閱讀 JSON，
   也不可只提供摘要或省略任何 property：
   - 先顯示 spec metadata table：`table_name`、`version`、`change_note`。
   - 顯示 common rules table，每個 field 一列：`name`、`dtype`、`nullable`、
     `invalid_value_tokens`、`confidence`、`source`。
   - 再依 dtype 顯示 type-specific tables：string 顯示 `unique`、`allow_empty_string`、
     `enum_values`、`pattern`；int/float 顯示 `min_value`、`max_value`；datetime 顯示
     `datetime_after`、`datetime_before`、`expected_datetime_format`。boolean 沒有額外規則。
   - `null`、空 array 或未設定值也必須以 `—`、`[]` 等清楚標記呈現，不可省略。
   - 表格後列出所有 medium/low-confidence assumptions 與 residual risk。
2. 要求使用者明確確認表格所代表的完整 exact spec version。只接受清楚的肯定回覆，例如 `confirm`、
   `confirmed`、`looks good`、`可以`、`確認` 或 `沒問題`。
3. 不可將沉默、部分回應或一般討論視為確認。
4. 使用者在確認後修改任何規則時，將 spec 標為未確認，回到
   `validation-field-spec`，然後重新取得確認。
5. Agent 必須在內部保留與表格完全對應的 canonical JSON。確認後將該 JSON 原樣交給
   `validation-artifact-delivery`；產生前不可修改或補值。
