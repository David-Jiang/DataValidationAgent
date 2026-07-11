# Safety Rules

- 不可發明 unsupported `field_spec` properties。
- 不可在任何 MCP tool 回傳 `ERROR:` 後繼續後續 workflow。
- 不可在使用者確認 final `field_spec` 前產生 mock data 或 validation suite。
- 除非使用者明確要求，不可直接寫入 production 或 local database。
- 除非已檢查相關 `great_expectations` 版本，否則不可宣稱 generated suite
  一定相容於使用者的 ETL runtime。
- MCP server 是 stateless。對話狀態、草稿、產生的 CSV 與 validation suite 檔案，
  必須由 agent 在 workspace 或對話中管理。
