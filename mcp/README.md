# Data Validation Agent — MCP Server

此 MCP Server 提供 DataHub schema、field-spec 規格、人工確認關卡、Great Expectations
suite、全反向 mock data 與 field-spec CSV 產生能力，並以記憶體內的狀態機強制 workflow
順序。

完整 Agent 流程與狀態機圖請見 [Agent 套件 README](../agent/README.md)。

## 專案結構

```text
mcp/
├── server.py
├── core/
│   ├── workflow.py
│   ├── models.py
│   ├── datahub_client.py
│   ├── field_spec_csv.py
│   ├── mock_data.py
│   ├── validation_suite.py
│   └── schemas/field_spec.schema.json
├── tests/
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
└── redeploy.sh
```

## Workflow 工具

| 工具 | 功能 |
| --- | --- |
| `start_validation` | 建立 workflow 並回傳 `workflow_id` |
| `get_validation_state` | 讀取 state、hash、事件歷程與 artifact 狀態 |
| `get_table_schema` | 依 workflow 保存的 URN 查詢 DataHub |
| `get_field_spec` | 回傳具權威性的 JSON Schema 並進入草擬階段 |
| `submit_field_spec` | 驗證並保存正式版 spec |
| `confirm_field_spec` | 記錄人工確認與實際 spec hash |
| `gen_validation_suite` | 只使用 Server 內已確認的 spec 產生 suite |
| `gen_mock_data` | 只使用 Server 內已確認的 spec 產生固定的全反向 CSV |
| `gen_field_spec_csv` | 將 Server 內已確認的正式版 spec 展開為 CSV |
| `complete_validation` | 記錄 Agent 已寫入並驗證的 workspace 路徑 |
| `resume_validation` | 修正作業錯誤後恢復 blocked workflow |

Artifact 產生器不再接受任意 `field_spec_json`。只有目前 workflow 中的確認 hash 與正式版
spec hash 相同時才能執行。

`workflow_id` 格式為 `dva_{YYYYMMDD}_{四碼 base36 suffix}`，日期使用 UTC。隨機選擇起始
suffix 後，若發生碰撞便依序探查下一個 suffix，確保目前 process 內唯一。

## 記憶體內儲存

`core/workflow.py` 的 module-level `workflow_store` 是行程內的全域 map：

```text
workflow_id -> workflow record
```

每筆紀錄保存 dataset URN、schema、規格 hash、正式版 field spec、確認紀錄、產生狀態、交付
路徑、blocked 恢復 state 與事件歷程。Artifact 內容不保存在 map 中。

這是 POC 設計：Server 重啟會遺失所有 workflow，且多個 replica 不共享狀態。

## Artifact 路徑

Agent Host 必須將 tool 回傳內容寫到使用者 workspace：

```text
artifacts/{workflow-id}/<table_name>_validation_suite.json
artifacts/{workflow-id}/<table_name>_mock.csv
artifacts/{workflow-id}/<table_name>_field_spec.csv
```

`complete_validation` 會驗證登記的相對路徑是否符合上述 workflow 專屬路徑，但
不會存取 Agent Host workspace 或保存檔案。

Field-spec CSV 固定包含：`table_name`、`name`、`dtype`、`nullable`、`unique`、
`allow_empty_string`、`enum_values`、`pattern`、`min_value`、`max_value`、
`datetime_after`、`datetime_before`、`expected_datetime_format`、
`invalid_value_tokens`、`confidence` 與 `source`。每個資料欄位各占一列。

## 環境設定

建立 `.env` 並填入 DataHub 設定：

```bash
cp .env.example .env
```

## 建置與部署

```bash
chmod +x redeploy.sh
./redeploy.sh
```

Server 啟動位址：

```text
http://127.0.0.1:{port}/mcp
```

POC state 只存在目前行程；每次重新部署都會清除所有 workflow。

## 測試

```bash
pip install -r requirements-dev.txt
pytest
```

目前的 Docker 執行環境固定為 Python 3.10.12。已在此版本中安裝完整開發依賴並執行全部
測試，確認 Great Expectations 1.18.2、MCP Server 與狀態機均可正常運作。

## 注意事項

- `gen_mock_data` 不接受筆數參數。基準為 100 筆；規則案例超過 100 時擴充至足以覆蓋全部
  案例，最多 1000 筆，超出的案例直接截斷且不報錯。
- Mock data 每列至少注入一條規則違規，固定作為 ETL 與 validation suite 的反向測試資料。
- Validation suite JSON、mock CSV 與 field-spec CSV 都是必要 artifacts。
- `unique` 只適用於 string field。
- Mock data 不會寫入資料庫。
- 本專案固定使用 Great Expectations 1.18.2。
- 修改 JSON Schema 後必須同步更新 Pydantic model 與規格測試。
