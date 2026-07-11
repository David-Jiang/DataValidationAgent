# Output Mode 與 Artifact Delivery

根據執行環境選擇 output mode：

- `workspace mode`：適用於 Cline、Codex、Claude Code、IDE agent，或任何可寫入使用者
  workspace filesystem 的環境。可將 artifacts 寫入檔案。
- `chat mode`：適用於純 chatbot 問答環境。不可宣稱已寫入檔案，只能回傳文字內容。

若環境能力不明確，詢問使用者要「寫入目前 workspace」或「以文字內容回傳」。

`workspace mode` 預設檔案結構：

```text
validation/
  field_specs/
    <table_name>.field_spec.json
  suites/
    <table_name>_validation_suite.json
  mock_data/
    <table_name>_mock.csv
```

`chat mode` 回傳 artifact 時，必須標示建議檔名，並使用 fenced code block：

- `field_spec`：`json`
- `validation_suite`：`json`
- `mock_data`：`csv`

產生 mock data 時，提醒使用者 CSV 是給他們自行 import 到自己的 local database。
