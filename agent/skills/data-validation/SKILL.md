---
name: data-validation
description: 統籌完整的 DataHub 資料表驗證流程，包含上游結構擷取、欄位規格定義、人工確認，以及 Great Expectations 或模擬資料產物交付。當使用者呼叫 /data-validation、提供 DataHub dataset URN，或要求 data validate、資料驗證、資料表驗證、定義欄位驗證規則、建立模擬資料、產生 Great Expectations validation suite 時使用。若需求相關但沒有 dataset URN，要求使用者提供。
---

# 資料驗證

將此 Skill 作為資料驗證 workflow 的唯一入口。每次流程只保留一個
`workflow_id`，並將它傳給所有 MCP 工具。未符合下列狀態機前置條件時，不可呼叫階段
工具。

## 必要流程

1. 若使用者未提供 DataHub dataset URN，要求使用者提供，此時不要呼叫任何 MCP 工具。
2. 讀取 [dataset-intake.md](references/dataset-intake.md)，呼叫
   `start_validation(dataset_urn)`，保留回傳的 `workflow_id`，再完成 schema 接收。
3. 讀取 [field-spec.md](references/field-spec.md)，完成 field spec 的討論與提交。
4. 讀取 [confirmation-gate.md](references/confirmation-gate.md)，顯示 `workflow_id` 與完整的
   已提交 spec。只有在使用者明確確認後，才可呼叫 `confirm_field_spec`。
5. 讀取 [artifact-delivery.md](references/artifact-delivery.md)，產生必要的 validation suite
   與選用的 mock data，寫入使用者 workspace、完成驗證，並將 workflow 標記為完成。

當狀態轉換遭拒、工具回傳 `ERROR:`、使用者變更 dataset 或已提交規則，或 workflow 必須
恢復時，讀取 [state-machine.md](references/state-machine.md)。

## 不可違反的規則

- 將 MCP workflow state 視為唯一事實來源。不可模擬、跳過或在本機覆寫 state。
- `get_table_schema` 成功前，不可建立資料表專屬規則。
- 草擬新 spec 前先呼叫 `get_field_spec`。已提交或確認後再次呼叫此工具，會刻意使舊的
  確認紀錄與已產生 artifact 狀態失效。
- 不可根據推測的同意呼叫 `confirm_field_spec`。只有完整、實際提交的 spec 已顯示，且使用者明確
  回覆 `確認`、`可以`、`沒問題`、`confirm`、`confirmed` 或 `looks good` 等肯定語句時，
  才可呼叫。
- 不可將使用者或模型提供的 spec 直接傳入產生器。產生器只讀取 MCP Server 保存且已確認的
  正式版 spec。
- 任一工具回傳以 `ERROR:` 開頭時立即停止，說明錯誤並等待修正後的輸入或環境。修正後
  檢查 workflow state，只有 state 為 `blocked` 時才呼叫 `resume_validation`。
- 不可將 mock data 寫入資料庫。
