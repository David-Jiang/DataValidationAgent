# Data Validation Agent — MCP Server

提供四個 MCP tools，供共用 Agent Host 依照 Data Validation workflow 與 DataHub、
Great Expectations 互動。

---

## 專案結構

```
mcp/
├── server.py                     # MCP Server 入口,定義四個工具
├── core/                         # 核心邏輯模組
│   ├── __init__.py               # 導出主要函式
│   ├── models.py                 # field_spec Pydantic 驗證模型
│   ├── mock_data.py              # 依 field_spec 產生 mock data (CSV)
│   ├── validation_suite.py       # 依 field_spec 產生 GE Validation Suite (JSON)
│   ├── datahub_client.py         # DataHub GraphQL API client
│   └── schemas/
│       └── field_spec.schema.json # field_spec 格式的正式 JSON Schema 定義
├── tests/                        # 單元測試
├── requirements.txt
├── Dockerfile
├── .env.example                  # 環境變數範本
├── .env                          # 實際環境變數
└── redeploy.sh                   # 一鍵重新 build & 啟動 container
```

---

## 四個工具說明

| 工具                   | 職責                                                             |
| ---------------------- | ---------------------------------------------------------------- |
| `get_table_schema`     | 呼叫 DataHub API,取得上游 table 的原始 schema                    |
| `get_field_spec`       | 回傳 field_spec 的正式 JSON Schema 定義,供討論時作為格式依據     |
| `gen_mock_data`        | 依確認後的 field_spec 產生符合欄位規則的 mock data,回傳 CSV 字串 |
| `gen_validation_suite` | 依確認後的 field_spec 產生 GE Expectation Suite,回傳 JSON 字串   |

本 Server 完全 **stateless**，不持有任何討論狀態。它在 MCP initialization 只提供輕量
server usage instructions；這些 instructions 是 client hint，不是 system prompt，也無法
強制 workflow。

---

## 環境設定

建立 `.env` 並填入填入正確的值

```bash
cp .env.example .env
```

---

## Build & Deploy

```bash
chmod +x redeploy.sh   # 第一次使用前給予執行權限
./redeploy.sh
```

`redeploy.sh` 會依序執行以下步驟:

1. 載入 `.env` 環境變數並驗證必填項目
2. 停止並移除舊的 container(若存在)
3. 重新 build Docker image
4. 以新 image 啟動 container

啟動後 MCP Server 運行於：`http://127.0.0.1:{port}/mcp`

**每次修改 server 程式碼後,重新執行** `./redeploy.sh` **即可完成重新部署。**

## Test

安裝 `requirements.txt` 後，在 repository root 執行：

```bash
PYTHONPATH=mcp python -m unittest discover -s mcp/tests -v
```

---

## 常用指令

```bash
# 查看 server log(即時)
docker logs -f dva-mcp

# 停止 server
docker stop

# 確認 container 狀態
docker ps | grep dva-mcp
```

---

## 注意事項

- `gen_mock_data` 只產生符合 field spec 的正向資料並回傳 CSV 內容字串，不會直接寫入任何
  資料庫。未指定 `row_count` 時預設產生 100 筆；使用者指定正整數時依指定數量產生，
  不另設上限。`unique` 僅適用於 string field。
- `gen_validation_suite` 依賴的 `great_expectations` 套件版本,需與 Airflow repo 中實際執行驗證的版本保持一致,避免 Expectation Suite 格式不相容。
- 修改 `core/schemas/field_spec.schema.json` 後,記得同步更新 `core/models.py` 裡的 Pydantic 模型,兩者目前是手動保持同步。
