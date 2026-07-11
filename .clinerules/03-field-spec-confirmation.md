# Field Spec 討論與確認 Gate

討論每個欄位時，至少確認：

- `dtype`
- `nullable`
- `unique`
- invalid tokens
- enum、pattern、numeric range 或 datetime format 等型別相關規則
- `confidence`
- `source`

必須區分 upstream schema fact 與 business expectation。DataHub nullable/type metadata
不能在未經使用者 review 的情況下直接視為最終 business contract。

產生任何 artifact 前，必須先呈現 final `field_spec` 摘要並請使用者確認。

只有明確確認才可接受，例如：

- `confirm`
- `confirmed`
- `looks good`
- `可以`
- `確認`
- `沒問題`

不可根據沉默、暗示同意或部分同意進入 generation。

若使用者在確認後修改任何規則，該 `field_spec` 必須重新視為未確認，
直到使用者再次確認。
