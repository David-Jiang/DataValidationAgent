---
name: validation-field-spec
description: 載入權威 field_spec contract，草擬或修改 field_spec，並與使用者釐清 validation semantics。使用於 schema intake 成功後，或使用者要求建立、修改欄位 validation rules 時。
---

# Field Spec 草擬

1. 草擬或修改 `field_spec` 前，先呼叫 `get_field_spec()`；回傳的 JSON Schema 優先於
   此 skill 與所有 repository 文件。
2. 若回應以 `ERROR:` 開頭，說明錯誤後停止，直到錯誤被修正。
3. 根據成功取得的 upstream metadata、使用者提供的 samples、領域文件與討論建立草稿。
   MCP server 是 stateless；草稿必須保留在 Agent Host 的對話狀態或選定輸出位置。
4. 只有直接來自 upstream metadata 的事實可使用 `source: "upstream_schema"`；使用者
   提供或確認的 business expectation 使用 `source: "discussed_with_user"`。
5. 未解決的假設標示為 `confidence: "medium"` 或 `"low"`；不可發明 schema 不支援的
   properties 或 values。
6. 只針對完成 contract 所缺少的語意提問：nullable、string uniqueness、invalid-value tokens、
   空字串、enum、pattern、numeric range 與 datetime bounds 或 format。`unique` 只適用於
   string field，不可加入 int、float、datetime 或 boolean field。較清楚時採逐欄
   review。
7. 確保每個 field 包含 required common properties，且只含 JSON Schema 允許的
   dtype-specific properties。除非使用者確認不同規則，invalid-value tokens 以
   `["NULL", "null", "NA", "None", "none"]` 為起點。
8. 草稿完成後，摘要列出 fields、version、change note 與 low-confidence rules，交給
   `validation-confirmation-gate`；此 skill 不可產生 artifact。
