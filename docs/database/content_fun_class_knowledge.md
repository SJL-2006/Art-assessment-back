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
