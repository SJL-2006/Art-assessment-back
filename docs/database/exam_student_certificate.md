# exam_student_certificate

- **表名**：exam_student_certificate
- **变更类型**：表新建
- **SQL 语句**：
  ```sql
  RENAME TABLE `exam_uploaded_certificate` TO `exam_student_certificate`;
  ```
- **修改日期**：2026-11-19 19:41:40
- **修改人**：userName

## 变更说明

由 `exam_uploaded_certificate` 重命名而来（原表记录见 `exam_uploaded_certificate.md`）。
模型 `UploadedCertificate` 重命名为 `StudentCertificate`（学生上传证书，待教师审核）。
字段与索引不变，数据随表名自动迁移（1 行）。

- `student`：上传学生（外键 users_user，级联删除；`related_name` 由 `uploaded_certificates` 改为 `student_certificates`）
- `reviewer`：审核人（外键 users_user，可空；`related_name` 保持 `reviewed_certificates`）
- 其余字段（title / cert_type / subject / issuer / obtained_at / image / note / status / review_comment / reviewed_at）与原表一致。

## 回滚方案

```sql
RENAME TABLE `exam_student_certificate` TO `exam_uploaded_certificate`;
```
