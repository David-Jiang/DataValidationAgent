# 人工確認關卡

必要起始 state：`awaiting_confirmation`。

先呼叫 `get_submitted_validation_rules(workflow_id)`，只使用其實際回傳內容建立 review 畫面；
不可改用草稿或要求使用者閱讀原始 JSON。

1. 顯示 workflow ID、dataset URN、table name 與 col/row/total rule counts。
2. 建立 `Column Rules` 區塊。每個欄位使用一個 `<details>`，summary 顯示欄位名稱、dtype 與
   規則數；展開後的 table 顯示 Rule ID、描述、使用欄位、Passing examples、Failing examples。
3. 建立 `Cross-field Row Rules` `<details>`。同樣使用 table 顯示所有 row rules；若為空，
   明確顯示 0 條與「本次沒有跨欄位規則」。
4. examples 必須同時顯示 name 與 SQL expression，不省略空集合或未設定值。
5. 提醒使用者本次確認同時涵蓋 col rules 與 row rules，請回覆「確認」或提供修改意見。
6. 只有收到清楚肯定回覆後，才呼叫 `confirm_validation_rules(workflow_id)`。

沉默、問題、部分意見或只確認其中一組都不算接受。任何修改都會使既有確認失效，必須重新
提交並重新顯示兩組完整 tables。

完成條件：`confirm_validation_rules` 成功，workflow 進入 `confirmed`。
