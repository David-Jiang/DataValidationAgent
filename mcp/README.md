# Data Validation Agent — MCP Server

此 MCP Server 將 DataHub schema、既有 `field_spec` 欄位模板與使用者討論出的跨欄位規則，
整理成可確認、可移植的 validation-as-code package。

完整 Agent 流程請見 [Agent 套件 README](../agent/README.md)。

## 核心資料契約

`validation_rules.json` 包含：

- `input_schema`：每欄只保存 `name`、`dtype`。
- `col_rules`：由 `core/schemas/field_spec.schema.json` 與正式版 field spec 確定性產生。
- `row_rules`：由使用者以自然語言、SQL 或其他方式說明後，經 Agent 正規化產生。
- 每條 rule 只保存 `id`、`desc`、`columns`、`examples`。`examples.pass` 與
  `examples.fail` 的項目格式皆為 `{"name": "...", "sql": "..."}`。

`examples.sql` 是協助人類 review 的 boolean expression，Server 與產生的 runtime 都不會
執行它，因此不會形成 SQL injection 執行路徑。

## Core 模組責任

| 模組                       | 責任                                                                                  |
| -------------------------- | ------------------------------------------------------------------------------------- |
| `core/field_spec.py`       | 解析並驗證 field spec 與各 dtype 的 column-specific 欄位                              |
| `core/rules.py`            | 建立 col rules、解析 row rules，並產生完整 semantic `ValidationRules`                 |
| `core/validation_rules.py` | 驗證 row rule 實作，並依 `ValidationRules` 產生 Pandas 驗證程式碼與 pytest 測試程式碼 |
| `core/artifacts.py`        | 只接受 `ValidationRules`，render 四項 artifact 內容                                   |
| `core/datahub.py`          | 查詢 DataHub GraphQL API 並正規化 dataset schema                                      |
| `core/workflow.py`         | 管理 workflow state、confirmation hash、artifact 狀態與歷程                           |

## Workflow 工具

| 工具                             | 功能                                             |
| -------------------------------- | ------------------------------------------------ |
| `start_validation`               | 建立 workflow 並回傳 `workflow_id`               |
| `get_validation_state`           | 讀取 state、hash、事件與 artifact 狀態           |
| `get_table_schema`               | 依 workflow 保存的 URN 查詢 DataHub              |
| `get_field_spec`                 | 回傳 col-rule 模板並進入 `drafting_rules`        |
| `submit_validation_rules`        | 驗證 field spec、建立 col rules 並保存 row rules |
| `get_submitted_validation_rules` | 取得待確認的完整 col/row rules                   |
| `confirm_validation_rules`       | 記錄完整 rules 與 field spec 的人工確認 hash     |
| `gen_validation_rules`           | 產生 `validation_rules.json`                     |
| `gen_readme`                     | 產生中文規則摘要與分組表格                       |
| `gen_data_validation`            | 產生 Pandas-native `data_validation.py`          |
| `gen_test_data_validation`       | 產生每條規則皆有 pass/fail case 的 pytest        |
| `record_pytest_result`           | 記錄使用者環境 pytest、production/test hashes 與輸出 |
| `complete_validation`            | 四個檔案寫入、讀回並通過 pytest 後登記完成       |
| `resume_validation`              | 修正作業錯誤後恢復 blocked workflow              |

Artifact generators 只讀取 Server 內已提交且已確認的 field spec 與 validation rules。重新
呼叫 `get_field_spec` 會使舊 confirmation 與 artifact 狀態失效。

`gen_data_validation` 首次成功後會保存 content SHA-256；相同內容可以 idempotent 重取，不同內容
會被拒絕。Agent 在使用者 repo 執行 pytest 後，必須呼叫 `record_pytest_result`，且提交的
`data_validation_sha256` 必須與凍結版本一致。測試檔可在失敗後修正並使用新 hash 重跑；
`complete_validation` 只接受最後一次成功 pytest 所對應的 production/test hashes。

## 人工確認關卡

Agent 必須先呼叫 `get_submitted_validation_rules`，將全部 `col_rules` 與 `row_rules` 分成兩組
可展開的 Markdown tables 顯示，包含 passing/failing SQL examples。只有使用者明確確認兩組
規則後，才能呼叫 `confirm_validation_rules`。

## Artifact 路徑

```text
artifacts/{workflow-id}/validation_rules.json
artifacts/{workflow-id}/README.md
artifacts/{workflow-id}/data_validation.py
artifacts/{workflow-id}/test_data_validation.py
```

`data_validation.validate(df)` 回傳 `(valid_df, invalid_df)`。空 DataFrame 會在任何 schema 或
rule evaluation 前直接回傳兩個空 DataFrame。非空資料若違反規則或執行規則時發生例外，
不會向呼叫端 raise；資料會進入 `invalid_df`，並附加 `__validation_failed_rules__` 與
`__validation_failure_reasons__`。

產生的 pytest 包含每條 col/row rule 至少一個 passing case 與 failing case，以及空
DataFrame shortcut；不產生 execution-failure 測試。pytest 實際在 Agent 可存取的使用者環境
執行，MCP 只保存證據與約束 state transition，不要求 Client 安裝 LangGraph 或額外 runtime。

## 記憶體內儲存

`core/workflow.py` 的 module-level `workflow_store` 是 process-local map。它保存 dataset URN、
upstream schema、field spec/rules hash、人工確認、artifact hashes、pytest 證據、artifact
狀態與歷程，不保存 artifact 內容。這是 POC 設計：Server 重啟會遺失 workflow，多個 replica
也不共享狀態。

## 環境與測試

```bash
cp .env.example .env
pip install -r requirements-dev.txt
pytest
```

部署可執行：

```bash
chmod +x redeploy.sh
./redeploy.sh
```

修改 field-spec JSON Schema 後，必須同步更新 Pydantic model、col-rule generator 與測試。
