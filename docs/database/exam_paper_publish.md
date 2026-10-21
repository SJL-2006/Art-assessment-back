# exam_paper_publish

- **表名**：exam_paper_publish
- **变更类型**：字段添加
- **SQL 语句**：
  ```sql
  ALTER TABLE exam_paper_publish ADD COLUMN grade VARCHAR(32) NOT NULL DEFAULT '';
  ```
- **修改日期**：2026-10-20 18:28:03
- **修改人**：userName

## 变更说明

新增 `grade`（年级）字段，用于 `scope_type=grade` 时记录发布目标年级；允许空、默认空字符串。
