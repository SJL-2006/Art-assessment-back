# exam_fun_content

- **表名**：exam_fun_content
- **变更类型**：表新建
- **SQL 语句**：
  ```sql
  CREATE TABLE "exam_fun_content" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "created_at" datetime NOT NULL,
    "updated_at" datetime NOT NULL,
    "is_deleted" bool NOT NULL,
    "deleted_at" datetime NULL,
    "title" varchar(128) NOT NULL,
    "subject" varchar(16) NOT NULL,
    "category" varchar(64) NOT NULL,
    "summary" varchar(255) NOT NULL,
    "content" text NOT NULL,
    "fun_fact" text NOT NULL,
    "emoji" varchar(16) NOT NULL,
    "color" varchar(16) NOT NULL,
    "read_minutes" integer NOT NULL,
    "status" varchar(16) NOT NULL,
    "published_at" datetime NULL,
    "creator_id" bigint NULL REFERENCES "users_user" ("id"),
    "school_id" bigint NULL REFERENCES "org_school" ("id"),
    "target_class_id" bigint NULL REFERENCES "classroom_class" ("id")
  );
  CREATE INDEX "exam_fun_content_creator_id_04fe496a" ON "exam_fun_content" ("creator_id");
  CREATE INDEX "exam_fun_content_school_id_9475c67b" ON "exam_fun_content" ("school_id");
  CREATE INDEX "exam_fun_content_target_class_id_b26d002f" ON "exam_fun_content" ("target_class_id");
  ```
- **修改日期**：2026-11-05
- **修改人**：highsun-max

## 变更说明

新建「趣味课堂内容」表，用于模块2（趣味课堂）功能。

- `title`：标题（最长 128）
- `subject`：学科（art/music/general，默认 general）
- `category`：分类（可空）
- `summary`：摘要（可空，最长 255）
- `content`：正文（可空）
- `fun_fact`：趣味小知识（可空）
- `emoji`：表情图标（可空）
- `color`：主题色（可空）
- `read_minutes`：阅读时长（默认 3 分钟）
- `status`：状态（draft/published，默认 draft）
- `creator`：创建人（外键 users_user，可空）
- `school`：目标学校（外键 org_school，可空）
- `target_class`：目标班级（外键 classroom_class，可空）
- `published_at`：发布时间（可空）
