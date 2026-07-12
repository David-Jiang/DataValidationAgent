# Data Validation Agent — Agent Host

本目錄是部署到共用 Agent Host 的 agent bundle。

Agent Host 管理對話狀態、workflow 與確認關卡；實際讀取 schema 和產生 artifacts 的能力
由 Data Validation Agent MCP Server 提供。

## 核心設計原則

- `SYSTEM_PROMPT.md` 只定義角色與能力邊界、跨階段必要流程、不可繞過的 guardrails
  及全域輸出規範。
- `skills/` 封裝各階段的領域知識、實作細節與操作步驟，並依職責呼叫必要的 MCP tools。
- MCP Server 提供 stateless tools，不保存草稿、確認狀態或 workflow 進度。

這項分工避免 system prompt、Skills、MCP instructions 與 client workspace instructions
各自形成一份互相漂移的 workflow 規範。

## 專案結構

```text
agent/
├── SYSTEM_PROMPT.md
└── skills/
    ├── validation-dataset-intake/
    │   ├── SKILL.md
    ├── validation-field-spec/
    │   ├── SKILL.md
    ├── validation-confirmation-gate/
    │   ├── SKILL.md
    └── validation-artifact-delivery/
        ├── SKILL.md
```

## 元件責任

| 元件                           | 責任                                                               | 不負責                                  |
| ------------------------------ | ------------------------------------------------------------------ | --------------------------------------- |
| `SYSTEM_PROMPT.md`             | 定義 agent 角色、必要 phase 順序、confirmation gate 與全域錯誤政策 | 欄位規則細節或 artifact 寫入步驟        |
| `validation-dataset-intake`    | 識別 dataset URN、取得並解讀 upstream schema                       | 推測缺少的 URN 或決定 business contract |
| `validation-field-spec`        | 載入權威 contract、草擬或修改 `field_spec`、釐清規則               | 確認 spec 或產生 artifact               |
| `validation-confirmation-gate` | 以完整可讀表格呈現 exact spec 並取得使用者明確確認                 | 顯示 JSON、只給摘要，或將一般討論視為確認 |
| `validation-artifact-delivery` | 依 confirmed spec 產生、儲存或回傳 artifacts                       | 修改 confirmed spec 或寫入 database     |
| MCP Server                     | 執行 DataHub 查詢、contract 讀取和 artifact 生成                   | 保存對話狀態或強制完整 workflow         |

## Skill 與 MCP Tool 對應

| Phase | Skill                          | MCP tool                                     | 完成條件                                  |
| ----- | ------------------------------ | -------------------------------------------- | ----------------------------------------- |
| 1     | `validation-dataset-intake`    | `get_table_schema`                           | 已成功取得指定 dataset 的 upstream schema |
| 2     | `validation-field-spec`        | `get_field_spec`                             | 已產生符合最新 JSON Schema 的待確認 spec  |
| 3     | `validation-confirmation-gate` | —                                            | 使用者明確確認呈現的 exact spec version   |
| 4     | `validation-artifact-delivery` | `gen_validation_suite`、選用 `gen_mock_data` | 已交付 artifacts 並說明 residual risk     |

## 必要 Workflow

```text
Dataset URN
    │
    ▼
validation-dataset-intake ── get_table_schema
    │ 成功取得 upstream schema
    ▼
validation-field-spec ────── get_field_spec
    │ 完成 field_spec 草稿與規則討論
    ▼
validation-confirmation-gate
    │ 使用者明確確認 exact version
    ▼
validation-artifact-delivery
    ├── gen_validation_suite（必要）
    └── gen_mock_data（使用者需要時）
```

以下 gate 不可略過：

1. `get_table_schema` 成功前，不可草擬 table-specific validation rules。
2. 建立或修改 `field_spec` 前，必須重新取得 `get_field_spec` 的權威 schema。
3. 使用者明確確認前，不可產生 artifacts。
4. 確認後若修改任何規則，原確認立即失效，必須回到 field-spec phase 並重新確認。
5. 任一 MCP tool 回傳以 `ERROR:` 開頭的內容時，立即停止 workflow；不可自行修改 spec
   後重試或繼續產生其他 artifact。

## 對話狀態與輸出

MCP Server 完全 stateless，因此 Agent Host 必須在對話狀態或使用者選定的位置保留：

- 成功取得的 dataset URN 與 upstream schema
- 當前 `field_spec` JSON、version 與 change note
- 尚未解決的 medium/low-confidence assumptions
- exact spec version 是否已由使用者明確確認

在可寫入 workspace 時，若使用者未指定輸出 root，預設交付結構為：

```text
validation/
├── field_specs/<version>_<table_name>_field_spec.json
├── suites/<table_name>_validation_suite.json
└── mock_data/<table_name>_mock.csv
```

若 Agent Host 只有 chat 輸出能力，應以個別 fenced code block 回傳 artifact 內容及建議
檔名，不可宣稱已寫入檔案。Agent 不會將 mock data 寫入 database。

## Agent Bundle Deployment

### 前置條件

- Data Validation Agent MCP Server 已啟動，且 Agent Host 可連線至其 MCP endpoint。
- 目標 Agent Host 支援載入 system prompt、Skills，以及呼叫 MCP tools。

### 部署步驟

1. 將 `SYSTEM_PROMPT.md` 設為 Data Validation Agent 的 system prompt。
2. 將 `skills/` 下四個完整 Skill 目錄註冊或掛載到同一個 Agent Host；保留目錄結構與
   Skill 名稱。
3. 將 Agent Host 連線到 Data Validation Agent MCP Server。
4. 確認 Agent 可發現以下四個 tools：`get_table_schema`、`get_field_spec`、
   `gen_mock_data`、`gen_validation_suite`。
5. 依下一節執行 smoke test，確認 workflow gate 由 Agent Host 正確執行。

```text
使用者 → Agent Host（SYSTEM_PROMPT + Skills）→ MCP Server → DataHub / artifact generators
```

使用者應與 Agent Host 對話，而不是直接使用 MCP Server。直接連線 MCP Server 只能取得
tools 與輕量 usage instructions，無法保證 workflow 順序、confirmation gate 或 Skill
行為。

## Smoke Test

部署後至少驗證以下情境：

1. 未提供 dataset URN：Agent 應要求使用者提供，不可自行推測。
2. 提供有效 URN：Agent 應先呼叫 `get_table_schema`，成功後才進入 field-spec phase。
3. 草擬 spec：Agent 應先呼叫 `get_field_spec`，並依回傳 contract 建立 JSON。
4. 尚未確認：要求產生 suite 時，Agent 應拒絕並先以完整表格呈現 final spec 取得明確確認。
5. 確認後修改規則：Agent 應使原確認失效並重新執行 confirmation gate。
6. MCP 回傳 `ERROR:`：Agent 應停止，不可繼續草擬、修改或產生 artifact。
7. 完成交付：Agent 應列出呼叫過的 tools、實際交付的 artifacts，以及仍存在的
   low-confidence field rules。

## 維護規則

- 修改跨階段流程或不可繞過的 guardrail：更新 `SYSTEM_PROMPT.md`，並檢查所有 Skills
  是否仍一致。
- 修改某一 phase 的操作方式：只更新對應的 `SKILL.md`。
- 修改 tool signature 或錯誤語意：先更新 MCP Server，再同步更新使用該 tool 的 Skill、
  `SYSTEM_PROMPT.md` 工具清單與本文件。
- 修改 `field_spec` contract：更新 MCP Server 的 JSON Schema 與 Pydantic model；不要在
  system prompt 或 Skill 中複製完整 schema。
- 新增 Skill 或 MCP tool 時，同步更新元件責任表、對應表、部署檢查與 smoke test。
