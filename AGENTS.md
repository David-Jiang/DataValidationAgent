# Data Validation Agent 操作指南

這個 repository 提供一個 stateless MCP server，用來在 ETL transform phase
之前，針對上游資料表建立 validation-as-code 資產。

Agent 的工作是和使用者協作，把上游 table schema、sample values、領域文件與討論結果，
整理成一份已確認的 `field_spec`。只有在使用者明確確認 final `field_spec` 之後，
agent 才能產生 mock data 或 Great Expectations validation suite。

## 單一事實來源

- `mcp/server.py` 內的 MCP tools 是目前可用工具的權威來源。
- `get_field_spec` 回傳的 JSON Schema 是 `field_spec` 格式的權威來源。
- `mcp/core/models.py` 是 `gen_mock_data` 與 `gen_validation_suite` 實際使用的 runtime validation model。
- MCP server 是 stateless，不保存討論狀態、草稿或版本歷史。
- 對話狀態、`field_spec` 草稿、產生的 CSV 與 validation suite 檔案，都應由 client agent
  在 ETL repository 或本機 workspace 中管理。

## 必要工作流程

1. 識別上游 dataset。
   - 如果使用者尚未提供 DataHub dataset URN，先向使用者詢問。
   - 在撰寫 table-specific validation rules 前，必須先呼叫 `get_table_schema(dataset_urn)`。
   - DataHub schema 只能視為起點，不能直接當作完整 validation spec。

2. 載入 `field_spec` contract。
   - 在建立或修改 `field_spec` 前，必須先呼叫 `get_field_spec()`。
   - 必須完全遵守工具回傳的 schema。
   - 不可自行發明 schema 未支援的欄位。

3. 草擬並討論 `field_spec`。
   - 根據 upstream schema、使用者提供的 sample values、文件與 business rules 建立草稿。
   - 對不確定的假設，使用 `confidence: "low"` 或 `confidence: "medium"` 明確標示。
   - 只有直接來自 upstream metadata 的事實，才能使用 `source: "upstream_schema"`。
   - 使用者提供或確認過的規則，使用 `source: "discussed_with_user"`。
   - 針對缺少的 business semantics 提出聚焦問題，例如 enum 值、invalid tokens、
     uniqueness、nullable 行為、日期格式、數值範圍、空字串行為與 table row count 預期。

4. 以使用者明確確認作為 gate。
   - 呼叫 `gen_mock_data` 或 `gen_validation_suite` 前，必須先整理 final `field_spec`
     摘要並請使用者確認。
   - 不可根據沉默、暗示同意或部分同意，從草稿階段進入產生階段。
   - 如果使用者在確認後又修改任何規則，該 `field_spec` 必須重新視為未確認，
     直到使用者再次確認更新後版本。

5. 決定 output mode。
   - 若 agent 運行在 Codex、Claude Code 或其他可讀寫 workspace filesystem 的環境，
     使用 `workspace mode`。
   - 若 agent 運行在純 chatbot 問答環境，無法可靠寫入使用者 codebase，
     使用 `chat mode`。
   - 若環境能力不明確，先詢問使用者希望「寫入目前 workspace」或「以文字內容回傳」。

6. 視需要產生 mock data。
   - 使用者確認後，才可呼叫 `gen_mock_data(field_spec_json, row_count)`。
   - 產生的 CSV 檔案是給使用者自行 import 到自己的 local database。
   - agent 不應直接寫入任何 database。

7. 產生 validation-as-code。
   - 使用者確認後，才可呼叫 `gen_validation_suite(table_name, field_spec_json)`。
   - 產生的 suite 目標是被 ETL codebase import，並以此 project 相容的
     `great_expectations` package family 執行。

## Output Mode

同一套 validation workflow 支援兩種 delivery 方式。差異只發生在「產出 artifact」階段；
前面的 schema fetching、field discussion、confirmation gate 都必須一致。

### Workspace Mode

適用於 Codex、Claude Code、IDE agent 或任何可操作使用者 workspace filesystem 的環境。

- 預設路徑為當前 root 並使用下方建議檔案結構。
- 寫檔後，回覆需列出實際檔案路徑。

### Chat Mode

適用於純 chatbot 問答環境，agent 無法寫入使用者本機檔案。

- 不宣稱已寫入檔案。
- 每個 artifact 都以獨立區塊回傳，並標示建議檔名。
- 建議格式：
  - `建議檔名：validation/field_specs/<table_name>.field_spec.json`
    使用 `json` code block 回傳 `field_spec`。
  - `建議檔名：validation/suites/<table_name>_validation_suite.json`
    使用 `json` code block 回傳 validation suite。
  - `建議檔名：validation/mock_data/<table_name>_mock.csv`
    使用 `csv` code block 回傳 mock data。

## 建議檔案結構

若使用者沒有指定位置，使用簡單且適合 Git 管理的 layout：

```text
validation/
  field_specs/
    <table_name>.field_spec.json
  suites/
    <table_name>_validation_suite.json
  mock_data/
    <table_name>_mock.csv
```

## Field Spec 撰寫規則

每個 field 必須包含：

- `name`
- `dtype`
- `nullable`
- `unique`
- `invalid_value_tokens`
- `confidence`
- `source`

支援的 `dtype`：

- `string`
- `int`
- `float`
- `datetime`
- `boolean`

型別專屬規則：

- `allow_empty_string` 與 `pattern` 只適用於 `dtype: "string"`。
- `min_value` 與 `max_value` 只適用於 `dtype: "int"` 或 `dtype: "float"`。
- `datetime_after`、`datetime_before` 與 `expected_datetime_format`
  只適用於 `dtype: "datetime"`。
- 不適用的型別專屬欄位，在需要明確表達時應設為 `null`，不可用未經說明的假設帶過。

目前 mock data generation 支援的常用 `semantic_tag` 包含：

- `uuid`
- `email`
- `phone`
- `currency`
- `timestamp`
- `free_text`
- `enum`
- `name`

## 協作方式

- 採取 iterative workflow。若逐欄討論更清楚，不要要求使用者一次定義整張表。
- Review field rules 時，優先使用精簡表格或分組問題。
- 只強調需要使用者決策的事項；已確認過的事實不要重複詢問。
- 區分 schema fact 與 business expectation。例如 upstream column 可能 nullable，
  但 ETL validation contract 可以要求 reject null。
- 當 spec version 變更時，在 `change_note` 中保留使用者意圖。

## Quality Gates

任務完成前必須確認：

- `field_spec` 可通過 MCP schema 驗證，或已被 `gen_mock_data` /
  `gen_validation_suite` 接受。
- 產生的檔案必須來自已確認的 `field_spec`，不能來自較早的草稿。
- 回覆中要說明寫入了哪些檔案，以及使用了哪些 command 或 MCP calls。
- 若仍有 unresolved low-confidence fields，必須明確列為 residual risk。
