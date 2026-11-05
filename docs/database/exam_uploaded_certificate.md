# exam_uploaded_certificate

- **表名**：exam_uploaded_certificate
- **变更类型**：表新建
- **SQL 语句**：
  ```sql
  CREATE TABLE "exam_uploaded_certificate" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "created_at" datetime NOT NULL,
    "updated_at" datetime NOT NULL,
    "is_deleted" bool NOT NULL,
    "deleted_at" datetime NULL,
    "title" varchar(128) NOT NULL,
    "cert_type" varchar(16) NOT NULL,
    "subject" varchar(16) NOT NULL,
    "issuer" varchar(128) NOT NULL,
    "obtained_at" date NULL,
    "image" varchar(100) NOT NULL,
    "note" text NOT NULL,
    "status" varchar(16) NOT NULL,
    "review_comment" text NOT NULL,
    "reviewed_at" datetime NULL,
    "reviewer_id" bigint NULL REFERENCES "users_user" ("id"),
    "student_id" bigint NOT NULL REFERENCES "users_user" ("id")
  );
  CREATE INDEX "exam_uploaded_certificate_reviewer_id_885159ea" ON "exam_uploaded_certificate" ("reviewer_id");
  CREATE INDEX "exam_uploaded_certificate_student_id_c080611a" ON "exam_uploaded_certificate" ("student_id");
  ```
- **修改日期**：2026-11-05
- **修改人**：highsun-max

## 变更说明

新建「学生上传证书」表，用于模块3（学生上传证书）功能。

- `student`：上传学生（外键 users_user，级联删除）
- `title`：证书标题（最长 128）
- `cert_type`：证书类型（exam/competition/graduation/other，默认 other）
- `subject`：学科（art/music/comprehensive/other，默认 other）
- `issuer`：颁发机构（可空）
- `obtained_at`：获得日期（可空）
- `image`：证书图片（必填，ImageField）
- `note`：备注（可空）
- `status`：审核状态（pending/approved/rejected，默认 pending）
- `reviewer`：审核人（外键 users_user，可空）
- `review_comment`：审核意见（可空）
- `reviewed_at`：审核时间（可空）
