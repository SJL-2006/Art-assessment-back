# org_school

- **表名**：org_school
- **变更类型**：字段添加
- **SQL 语句**：
  ```sql
  ALTER TABLE org_school ADD COLUMN is_directly_affiliated bool NOT NULL DEFAULT 0;
  ```
- **修改日期**：2026-10-28 15:55:33
- **修改人**：userName

## 变更说明

新增 `is_directly_affiliated`（市直属）字段，用于标记直接隶属市州、不隶属区县的学校；
默认 False，既有数据不受影响。市州端「创建/查询市直属学校账号」据此区分普通区县学校账号。

## 回滚方案

```sql
ALTER TABLE org_school DROP COLUMN is_directly_affiliated;
```
