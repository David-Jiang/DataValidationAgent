---
name: validation-confirmation-gate
description: 與使用者 review 完整 field_spec，並在產生 validation artifact 前強制取得明確確認。使用於 field_spec 可送審時，或先前已確認的規則被修改後。
---

# Field Spec 確認 Gate

1. 呈現 final `field_spec` 摘要：table name、version、change note、每個 field 的規則，
   以及剩餘的 medium- 或 low-confidence assumptions。
2. 要求使用者明確確認此 exact version。只接受清楚的肯定回覆，例如 `confirm`、
   `confirmed`、`looks good`、`可以`、`確認` 或 `沒問題`。
3. 不可將沉默、部分回應或一般討論視為確認。
4. 使用者在確認後修改任何規則時，將 spec 標為未確認，回到
   `validation-field-spec`，然後重新取得確認。
5. 確認後，原樣保留 confirmed JSON 並交給 `validation-artifact-delivery`；產生前不可
   修改它。
