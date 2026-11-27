# qb_question

- **表名**：qb_question
- **变更类型**：字段修改
- **SQL 语句**：
  ```sql
  ALTER TABLE `qb_question` MODIFY `qtype` varchar(16) NOT NULL;
  ```
- **修改日期**：2026-11-25 20:01:58
- **修改人**：userName

## 变更说明

题型字典收敛：`qtype` 字段的 `choices` 由 7 种（单选 `single` / 多选 `multiple` / 判断 `judge` / 填空 `fill` / 简答 `short` / 听力 `listening` / 视唱识谱 `sight`）收敛为 3 种（单选 `single` / 多选 `multiple` / 判断 `judge`），即题库只保留选择题与判断题。

列类型（`varchar(16)`）、长度、`NOT NULL` 约束、默认值均未改动，仅 `choices` 收敛。MySQL 下 `AlterField` 对应的 `MODIFY` 语句列定义未实质变化，属于同步 Django 迁移状态中的 `choices`。对应迁移 `apps/questionbank/migrations/0005_alter_question_qtype.py`。

## 回滚方案

如需恢复 7 种题型，将 `apps/questionbank/models.py` 中 `Question.TYPE_CHOICES` 恢复为 7 种后重新生成迁移即可（`python manage.py makemigrations questionbank`）。数据库列定义本就未改动，无需额外 DDL 回滚。
