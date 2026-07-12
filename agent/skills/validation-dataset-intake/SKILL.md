---
name: validation-dataset-intake
description: 識別上游 DataHub dataset 並取得來源 schema，再開始 table-specific validation。使用於使用者開始 validation 請求、提供或變更 dataset URN，或要求檢視上游 schema 時。
---

# 上游 Dataset Intake

1. 若使用者尚未提供 DataHub dataset URN，要求提供；不可自行推測或編造。
2. 提出 table-specific validation rules 前，先呼叫 `get_table_schema(dataset_urn)`。
3. 若回應以 `ERROR:` 開頭，說明錯誤後立即停止。等待可用的 URN 或修正後的 DataHub
   環境；不可呼叫下一個 workflow tool 或草擬 `field_spec`。
4. 將回傳的 column name、type、description 與 nullability 視為 upstream metadata，
   只作為討論輸入，不可直接視為最終 business contract。
5. 將成功取得的 schema，以及使用者提供的 samples 或 domain material，交給
   `validation-field-spec`。
