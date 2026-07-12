---
name: validation-artifact-delivery
description: 根據已明確確認的 field_spec，交付 canonical field spec、Great Expectations suite，以及使用者需要時的 mock CSV data。僅在 confirmation gate 已確認將要交付的 exact field_spec 後使用。
---

# Validation Artifact 交付

1. 必須確認 exact `field_spec` 已被明確確認且未變更；否則必須回到
   `validation-confirmation-gate`。
2. 每次完成的 workflow 必須交付以下 artifacts；validation suite 或 mock CSV **不得**取代
   canonical field spec：
   - **必要**：使用者確認的 canonical `field_spec` JSON。此檔案不需要 MCP generator，但仍
     必須交付，而且內容必須與確認時保留的 canonical JSON 完全一致。
   - **必要**：Great Expectations validation suite。
   - **條件必要**：使用者需要 mock data 時的 mock CSV。
3. 詢問使用者是否需要產生 mock data；需要且未指定筆數時，直接以預設 `row_count=100`
   呼叫 `gen_mock_data`，不可再追問筆數。使用者已明確指定正整數筆數時，原樣使用該數量，
   不另設上限。validation suite 不用詢問即呼叫
   `gen_validation_suite(table_name, field_spec_json)` 產生。
4. 任一回應以 `ERROR:` 開頭時，說明錯誤後停止。不可用修改後的 spec 重試，也不可
   生成其他 artifact，直到使用者處理錯誤並重新確認任何修改過的 spec。
5. MCP tool 成功回傳內容只代表 artifact **產生成功**，不代表 artifact **交付完成**。
6. Agent Host 只要具有 workspace 寫檔能力，就**必須**建立所需目錄，並將所有必要 artifact
   存到使用者選定的 root；未指定時**必須**使用：

   ```text
   validation/
     field_specs/<version>_<table_name>_field_spec.json
     suites/<table_name>_validation_suite.json
     mock_data/<table_name>_mock.csv
   ```

   寫入後必須讀回或以其他方式驗證每個必要檔案確實存在且內容正確，並回覆每個檔案的實際
   寫入路徑。未完成寫入與驗證前，禁止宣稱 workflow 或 artifact delivery 已完成。

   若 field spec 的預定檔名已存在，禁止在確認後直接改寫 version。必須先回到
   `validation-field-spec` 遞增 version，再以 `validation-confirmation-gate` 重新取得確認，之後
   才可產生及寫入 artifacts。

7. 只有 Agent Host 確實沒有任何 workspace 寫檔能力時，才可使用 chat-only mode；不得僅因
   MCP tool 以字串回傳內容，就自行判定為 chat-only mode。在 chat-only mode，不可宣稱已
   寫入檔案；每個必要 artifact 必須各自使用 fenced block 回傳，並標示建議檔名（spec 和
   suite 用 `json`，mock data 用 `csv`）。
8. 不可寫入 database。說明 CSV 由使用者自行匯入；除非已檢查目標 ETL runtime version，
   不可宣稱 Great Expectations 相容。
9. 宣稱完成前，必須逐項確認：
   - 已以完整 Markdown tables 呈現 exact `field_spec`，且使用者已明確確認。
   - 已交付 confirmed canonical field spec JSON。
   - 已交付 validation suite。
   - 使用者需要 mock data 時，已交付 mock CSV。
   - 在可寫入 workspace 中，每個必要檔案均已寫入並驗證。
10. 結束前，必須列出已呼叫的 MCP tools、每個已交付 artifact 的實際路徑或建議檔名，以及仍
    存在的 low-confidence field rules，作為 residual risk。
