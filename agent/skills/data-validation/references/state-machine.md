# Workflow 狀態機

| 狀態 | 允許的下一個操作 | 成功後 state |
| --- | --- | --- |
| `awaiting_schema` | `get_table_schema` | `dataset_ready` |
| `dataset_ready` | `get_field_spec` | `drafting_rules` |
| `drafting_rules` | `submit_validation_rules` | `awaiting_confirmation` |
| `awaiting_confirmation` | 顯示全部規則；明確確認後 `confirm_validation_rules` | `confirmed` |
| `confirmed` | 任一固定 artifact generator | `generating_artifacts` |
| `generating_artifacts` | 其餘 generators；`record_pytest_result`；通過後 `complete_validation` | 失敗時留在本 state；通過後 `completed` |
| `blocked` | 修正問題後 `resume_validation` | 已記錄的恢復 state |
| `completed` | 無 | 終止狀態 |

從 `awaiting_confirmation`、`confirmed` 或 `generating_artifacts` 再呼叫 `get_field_spec`，會
開始新的修改循環：清除 confirmation、validation rules 與 artifact 狀態，回到
`drafting_rules`。

固定 artifacts 為 `validation_rules`、`readme`、`data_validation`、
`test_data_validation`；缺少任一項時 `complete_validation` 必須拒絕完成。

`data_validation` 首次生成時保存 frozen SHA-256。pytest repair loop 可讓
`test_data_validation.py` hash 改變，但每次 `record_pytest_result` 的 production hash 必須保持
一致；最後一次成功 pytest 的兩個 hashes 必須與 `complete_validation` 完全相符。連續五次
失敗會進入 `blocked`，人工檢查後可 resume 回 `generating_artifacts`。

作業環境錯誤可把 workflow 移至 `blocked` 並保存恢復 state；輸入格式或非法 state transition
只回傳 `ERROR:`，不推進 state。修正後先呼叫 `get_validation_state`，只有 state 確實為
`blocked` 才呼叫 `resume_validation`。
