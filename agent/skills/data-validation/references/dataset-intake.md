# Dataset 接收

1. 要求使用者明確提供 DataHub dataset URN，不可推測或捏造。
2. 每次流程只呼叫一次 `start_validation(dataset_urn)`，並保留回傳的 `workflow_id`。
3. 告知使用者 workflow ID。
4. 當 state 為 `awaiting_schema` 時呼叫 `get_table_schema(workflow_id)`。
5. 將回傳的名稱、型別、說明、key 與 nullability 視為上游 metadata，不可直接視為
   最終業務規格。
6. 若 dataset URN 改變，建立新的 workflow，不可重用或覆寫既有 workflow。

完成條件：`get_table_schema` 成功，且 workflow 進入 `dataset_ready`。
