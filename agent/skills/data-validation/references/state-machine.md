# Workflow 狀態機

MCP Server 以 `workflow_id` 為 key，將所有 state 保存於記憶體內的 map。Server 重啟後會
遺失所有 POC workflow。不可在 Agent Host 重新建立或覆寫 state。

| 狀態 | 允許的下一個操作 | 成功後的 state |
| --- | --- | --- |
| `awaiting_schema` | `get_table_schema` | `dataset_ready` |
| `dataset_ready` | `get_field_spec` | `drafting_spec` |
| `drafting_spec` | `submit_field_spec` | `awaiting_confirmation` |
| `awaiting_confirmation` | 使用者明確確認，再呼叫 `confirm_field_spec` | `confirmed` |
| `confirmed` | `gen_validation_suite` 或 `gen_mock_data` | `generating_artifacts` |
| `generating_artifacts` | 產生剩餘 artifact 或呼叫 `complete_validation` | `completed` |
| `blocked` | 修正使用者輸入或環境，再呼叫 `resume_validation` | 已記錄的恢復 state |
| `completed` | 無 | 終止狀態 |

從 `awaiting_confirmation` 或 `confirmed` 呼叫 `get_field_spec` 會開始新的修改循環：清除
確認紀錄與 artifact 狀態，並將 state 改為 `drafting_spec`。

MCP 作業錯誤會將 workflow 移至 `blocked` 並記錄恢復 state。無效輸入或不合法的
state transition 會回傳 `ERROR:`，但不推進 state。使用者修正問題後，呼叫
`get_validation_state`；若 state 為 `blocked`，呼叫 `resume_validation`，否則只重試修正後的
操作。
