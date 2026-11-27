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

---

# 第二次变更：student_no / staff_no 增加索引

- **表名**：users_user
- **变更类型**：字段修改
- **SQL 语句**：
  ```sql
  ALTER TABLE `users_user` ADD INDEX `users_user_student_no_018146b6` (`student_no`);
  ALTER TABLE `users_user` ADD INDEX `users_user_staff_no_e479af5d` (`staff_no`);
  ```
- **修改日期**：2026-11-25 17:02:24
- **修改人**：userName

## 变更说明

为支持「成都真实学校数据」初始化产生的约 11.6 万学生 / 3484 教师账号的学号 / 工号登录查询，给 `student_no`、`staff_no` 增加普通索引，避免登录时按学号 / 工号全表扫描。字段类型、长度、默认值、约束均未改动，仅新增索引。对应迁移 `apps/users/migrations/0003_alter_user_staff_no_alter_user_student_no.py`。

## 回滚方案

```sql
ALTER TABLE `users_user` DROP INDEX `users_user_student_no_018146b6`;
ALTER TABLE `users_user` DROP INDEX `users_user_staff_no_e479af5d`;
```

---

# 第三次变更：teacher_type 字段添加

- **表名**：users_user
- **变更类型**：字段添加
- **SQL 语句**：
  ```sql
  ALTER TABLE `users_user` ADD COLUMN `teacher_type` varchar(16) NOT NULL DEFAULT '';
  ```
- **修改日期**：2026-11-25 18:50:34
- **修改人**：userName

## 变更说明

新增 `teacher_type`（教师类型）字段，用于区分教师角色下的两类身份：`head`（班主任）、`subject`（科任老师）。仅 `role=teacher` 的账号使用，其余角色（学生 / 学校 / 区县 / 市州 / 省级 / 题库管理员）保持空串默认值。字段允许为空、默认空串，既有数据不受影响。对应迁移 `apps/users/migrations/0004_user_teacher_type.py`。

## 回滚方案

```sql
ALTER TABLE `users_user` DROP COLUMN `teacher_type`;
```
