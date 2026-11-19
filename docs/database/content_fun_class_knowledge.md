# content_fun_class_knowledge

- **表名**：content_fun_class_knowledge
- **变更类型**：字段添加（新建表）
- **SQL 语句**（等价 DDL，以 Django 迁移文件为准）：
  ```sql
  CREATE TABLE content_fun_class_knowledge (
      id            BIGINT AUTO_INCREMENT PRIMARY KEY,
      title         VARCHAR(200) NOT NULL,
      subject       VARCHAR(16)  NOT NULL,
      content       LONGTEXT     NOT NULL,
      image         VARCHAR(100) NOT NULL,
      sort          INTEGER      NOT NULL,
      is_published  BOOL         NOT NULL,
      created_at    DATETIME(6)  NOT NULL,
      updated_at    DATETIME(6)  NOT NULL,
      is_deleted    BOOL         NOT NULL,
      deleted_at    DATETIME(6)  NULL
  );
  ```
- **修改日期**：2026-10-28 15:55:33
- **修改人**：userName

## 变更说明

新建「趣味课堂知识」表，用于学生端素质教育展示模块（趣味课堂知识展示）。
继承 BaseModel 公共字段（created_at / updated_at / is_deleted / deleted_at）。

## 回滚方案

```sql
DROP TABLE content_fun_class_knowledge;
```

---

## 表删除（2026-11-19）

- **表名**：content_fun_class_knowledge
- **变更类型**：表删除
- **SQL 语句**：
  ```sql
  DROP TABLE IF EXISTS `content_fun_class_knowledge`;
  DELETE FROM `django_migrations` WHERE `app` = 'content';
  DELETE FROM `django_content_type` WHERE `app_label` = 'content';
  ```
- **修改日期**：2026-11-19 19:41:40
- **修改人**：userName

### 变更说明

删除废弃的 `content` app 及其唯一表 `content_fun_class_knowledge`（0 行）。
该表与 `exam_fun_content` 功能重复，前端无任何调用（前端趣味课堂走 `/exam/fun-contents/`）。
同步清理迁移记录 `content.0001_initial` 与对应 ContentType 记录。
