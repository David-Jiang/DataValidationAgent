---
name: data-validation
description: 統籌 DataHub 資料表的 validation-as-code 流程：取得上游 schema、依 field_spec 建立 column rules、討論 cross-field row rules、人工確認全部規則，並交付 validation_rules.json、中文 README、Pandas-native data_validation.py 與 pytest。使用者呼叫 /data-validation、提供 DataHub dataset URN，或要求資料驗證、欄位規則、跨欄位商業規則或 Airflow validation unit tests 時使用。若缺少 dataset URN，先要求使用者提供。
---

# 資料驗證

將此 Skill 作為 workflow 的唯一入口；同一流程只使用一個 `workflow_id`。

## 必要流程

1. 缺少 DataHub dataset URN 時先向使用者索取，不呼叫 MCP tool。
2. 讀取 [dataset-intake.md](references/dataset-intake.md)，建立 workflow 並取得 schema。
3. 讀取 [field-spec.md](references/field-spec.md)，討論 field spec 所對應的 col rules，以及使用者
   用自然語言、SQL 或其他方式表達的 row rules，再一併提交。
4. 讀取 [confirmation-gate.md](references/confirmation-gate.md)，用分組、可展開的 tables 顯示
   全部 col rules 與 row rules。只有使用者明確確認兩組規則後才呼叫
   `confirm_validation_rules`。
5. 讀取 [artifact-delivery.md](references/artifact-delivery.md)，產生、寫入、讀回並測試四個固定
   artifacts，再將 workflow 標記完成。

狀態被拒、工具回傳 `ERROR:`、規則被修改或 workflow 需要恢復時，讀取
[state-machine.md](references/state-machine.md)。

## 不可違反的規則

- MCP workflow state 是唯一事實來源；不可模擬或跳過 state。
- `get_table_schema` 成功前不可建立 dataset-specific rules。
- 每次規則修改循環前呼叫 `get_field_spec`；此動作會使舊 confirmation 與 artifact 狀態失效。
- `row_rules` 每條只保存 `id`、`desc`、`columns`、`examples`；passing/failing example 都使用
  `{"name": "...", "sql": "..."}`。SQL 只供人類 review，不可執行。
- 不可把自然語言或 SQL 原文當成 Python 執行。row-rule implementation 必須依已確認語意重新
  撰寫成 pure Pandas body，交由 Server 檢查。
- 不可推測使用者已同意；必須完整顯示實際提交的 col/row rules 並收到明確肯定回覆。
- 產生器只讀取 Server 保存且已確認的正式版 rules。
- `data_validation.py` 首次生成後即凍結；保存 generator 回傳內容的 SHA-256。pytest 失敗時只
  可修改 `test_data_validation.py`，不可再次呼叫 `gen_data_validation` 產生不同內容。
- 每次使用者環境 pytest 都要提交真實 return code、command、output 與 production/test hashes
  給 `record_pytest_result`；只有最後一次成功證據可供完成 workflow。
- 不可用 skip/xfail、刪除 rule coverage 或弱化 assertions 讓測試虛假通過。若失敗源自
  production implementation，在不可修改 `data_validation.py` 的限制下應進入 `blocked`。
- 工具回傳 `ERROR:` 時停止該流程並說明錯誤；只有 state 為 `blocked` 時才呼叫
  `resume_validation`。
