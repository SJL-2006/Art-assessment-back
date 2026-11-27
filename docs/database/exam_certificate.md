# exam_certificate

- **表名**：exam_certificate
- **变更类型**：字段修改
- **SQL 语句**：
  ```sql
  ALTER TABLE exam_certificate ADD CONSTRAINT exam_certificate_student_sheet_uniq
    UNIQUE (student_id, sheet_id);
  ```
- **修改日期**：2026-11-26 10:41:47
- **修改人**：userName

## 变更说明

为 `exam_certificate`（证书）增加唯一约束 `(student_id, sheet_id)`：同一学生对同一答卷只允许发放一张证书。

- 依据：`issue_certificate` 用 `get_or_create(student, sheet, subject)` 自动发放，业务上同一答卷只应发一张证书，此前缺数据库层约束，重复触发可能产生重复证书。
- 影响范围：仅限制重复发放；历史数据若已存在重复需先人工去重再应用本迁移。
- 回滚方案：删除该唯一约束即可恢复：
  ```sql
  ALTER TABLE exam_certificate DROP INDEX exam_certificate_student_sheet_uniq;
  ```
