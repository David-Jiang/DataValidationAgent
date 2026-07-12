---
name: validation-artifact-delivery
description: 根據已明確確認的 field_spec 產生並交付 mock CSV data 或 Great Expectations suite。僅在 confirmation gate 已確認將要生成的 exact field_spec 後使用。
---

# Validation Artifact 交付

1. 確認 exact `field_spec` 已被明確確認且未變更；否則回到
   `validation-confirmation-gate`。
2. 詢問使用者是否需要產生 mock data ，需要時則呼叫 `gen_mock_data(field_spec_json, row_count)`；
   不用詢問使用者即產生 validation suite ，呼叫 `gen_validation_suite(table_name, field_spec_json)`。
3. 任一回應以 `ERROR:` 開頭時，說明錯誤後停止。不可用修改後的 spec 重試，也不可
   生成其他 artifact，直到使用者處理錯誤並重新確認任何修改過的 spec。
4. 在可寫入 workspace 中，將 artifact 存到使用者選定的 root；未指定時使用：

   ```text
   validation/
     field_specs/<version>_<table_name>_field_spec.json
     suites/<table_name>_validation_suite.json
     mock_data/<table_name>_mock.csv
   ```

   field spec 的預定檔名已存在時，遞增 version。回覆實際寫入路徑。

5. 在 chat-only mode，不可宣稱已寫入檔案。每個 artifact 各自使用 fenced block 回傳，
   並標示建議檔名（spec 和 suite 用 `json`，mock data 用 `csv`）。
6. 不可寫入 database。說明 CSV 由使用者自行匯入；除非已檢查目標 ETL runtime version，
   不可宣稱 Great Expectations 相容。
7. 結束前，列出已呼叫的 MCP tools、交付的 artifacts 與仍存在的 low-confidence field
   rules，作為 residual risk。
