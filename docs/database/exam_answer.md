# exam_answer

- **表名**：exam_answer
- **变更类型**：字段修改
- **SQL 语句**：
  ```sql
  ALTER TABLE exam_answer ADD CONSTRAINT exam_answer_sheet_question_uniq
    UNIQUE (sheet_id, question_id);
  ```
- **修改日期**：2026-11-26 10:41:47
- **修改人**：userName

## 变更说明

为 `exam_answer`（答题明细）增加唯一约束 `(sheet_id, question_id)`：同一份答卷同一道题只允许一条答题记录。

- 依据：`save_answers` 使用 `update_or_create(sheet, question_id)`、`submit_sheet` 也按 `(sheet, question)` 去重，业务上本就要求唯一，此前缺少数据库层约束兜底，并发保存可能产生重复行。
- 影响范围：仅限制重复写入；历史数据若已存在重复需先人工去重再应用本迁移。
- 回滚方案：删除该唯一约束即可恢复：
  ```sql
  ALTER TABLE exam_answer DROP INDEX exam_answer_sheet_question_uniq;
  ```
