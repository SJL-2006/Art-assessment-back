# users_user

- **表名**：users_user
- **变更类型**：字段添加
- **SQL 语句**：
  ```sql
  ALTER TABLE users_user ADD COLUMN staff_no varchar(64) NOT NULL DEFAULT '';
  ```
- **修改日期**：2026-11-11 12:43:09
- **修改人**：userName

## 变更说明

新增 `staff_no`（职工编号）字段，与 `student_no`（学籍号）并列：学生用学号登录，教师及各级管理员（学校/区县/市州/省级/题库管理员）用职工编号登录。字段允许为空、默认空串，既有数据不受影响；与 `student_no` 一致未设唯一约束。

## 回滚方案

```sql
ALTER TABLE users_user DROP COLUMN staff_no;
```
