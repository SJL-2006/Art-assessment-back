# 数据库变更记录 —— BaseModel 补充 deleted_at 字段

| 项目 | 内容 |
|---|---|
| 类型 | 字段添加 |
| 涉及表 | org_region, org_school, classroom_class, classroom_class_student, classroom_class_teacher, exam_answer, exam_answer_sheet, exam_certificate, exam_paper, exam_paper_publish, exam_paper_question, questionbank_chapter, questionbank_course, questionbank_question, questionbank_question_resource, questionbank_question_review |
| 修改日期 | 2026-10-20 17:09 |
| 修改人 | highsun-max |
| 规范依据 | 《后端开发规范》第 177 行：软删除使用 is_deleted + deleted_at |

---

## 背景

项目初始化时 BaseModel 抽象基类仅有 `is_deleted`（BooleanField），缺少规范要求的 `deleted_at`（DateTimeField）。为统一软删除行为，本次补充该字段。

## SQL（等价迁移）

```sql
ALTER TABLE org_region ADD COLUMN deleted_at datetime NULL;
ALTER TABLE org_school ADD COLUMN deleted_at datetime NULL;
ALTER TABLE classroom_class ADD COLUMN deleted_at datetime NULL;
ALTER TABLE classroom_class_student ADD COLUMN deleted_at datetime NULL;
ALTER TABLE classroom_class_teacher ADD COLUMN deleted_at datetime NULL;
ALTER TABLE exam_answer ADD COLUMN deleted_at datetime NULL;
ALTER TABLE exam_answer_sheet ADD COLUMN deleted_at datetime NULL;
ALTER TABLE exam_certificate ADD COLUMN deleted_at datetime NULL;
ALTER TABLE exam_paper ADD COLUMN deleted_at datetime NULL;
ALTER TABLE exam_paper_publish ADD COLUMN deleted_at datetime NULL;
ALTER TABLE exam_paper_question ADD COLUMN deleted_at datetime NULL;
ALTER TABLE questionbank_chapter ADD COLUMN deleted_at datetime NULL;
ALTER TABLE questionbank_course ADD COLUMN deleted_at datetime NULL;
ALTER TABLE questionbank_question ADD COLUMN deleted_at datetime NULL;
ALTER TABLE questionbank_question_resource ADD COLUMN deleted_at datetime NULL;
ALTER TABLE questionbank_question_review ADD COLUMN deleted_at datetime NULL;
```

Django 自动生成的迁移文件：
- `apps/classroom/migrations/0004_classroom_deleted_at_classstudent_deleted_at_and_more.py`
- `apps/exam/migrations/0004_answer_deleted_at_answersheet_deleted_at_and_more.py`
- `apps/org/migrations/0002_region_deleted_at_school_deleted_at.py`
- `apps/questionbank/migrations/0003_chapter_deleted_at_course_deleted_at_and_more.py`

## 回滚方案

```bash
python manage.py migrate classroom 0003
python manage.py migrate exam 0003
python manage.py migrate org 0001
python manage.py migrate questionbank 0002
```

或等价 SQL：
```sql
ALTER TABLE org_region DROP COLUMN deleted_at;
-- ... 其余表同理
```

## 影响范围

- 字段新增，不影响现有数据
- BaseViewSet.perform_destroy 已改为写入 deleted_at=now()
- 所有继承 BaseModel 的模型自动获得软删除能力

## 备注

User 模型继承 AbstractUser（非 BaseModel），无 deleted_at 字段。账号模块的软删除统一使用 `is_active=False`，与规范约定的"is_deleted + deleted_at"方案并行（因 User 模型已冻结不再修改）。
