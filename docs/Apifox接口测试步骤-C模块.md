# C 模块（作答·判分·评分·统计·证书）Apifox 测试文档

> 适用对象：负责验收成员 C 交付的 26 个接口（测评作答、判分评分、学生端结果、数据统计、证书）。
> 每个接口都给出 **接口名、方法/路径、角色、请求 JSON、响应 JSON 字段**，按「准备 → 导入 → 认证 → 分链路逐步测试」顺序操作即可跑通全链路。

---

## 〇、接口总览

C 模块共 **26 个业务接口**（+ 登录/刷新 2 个认证接口），按调用角色分 5 组：

| 组 | 接口 | 数量 | 调用角色 |
| --- | --- | --- | --- |
| 测评作答 | #1-#5（+记录 #13、报告 #12） | 5 | 学生 |
| 判分与评分 | #6-#11、#21 | 6 | 教师 / 学校 |
| 学生端结果 | #14-#17 | 4 | 学生 |
| 数据统计 | #18-#20 | 3 | 学校 / 区县 / 市州 / 省级 |
| 证书 | #22-#26 | 5 | 学生 / 教师 / 学校 |

---

## 一、前置准备（跑起来）

### 1.1 先修团队遗留的迁移冲突（重要）

`exam` 应用有 3 个 `0004_*` 迁移互相冲突，且 `org`/`classroom`/`questionbank` 的 `deleted_at` 迁移没应用到开发库。在 `backend/` 依次执行：

```bash
python manage.py makemigrations --merge --noinput   # 生成 exam/0005_merge，解决三叉冲突
python manage.py migrate                            # 把 pending 迁移落库
```

验证：`python manage.py migrate --plan` 无待执行迁移。

### 1.2 初始化演示数据

```bash
python manage.py seed_demo
```

幂等命令，一次性造好完整数据链：

```
四川省(province) → 成都市(city) → 锦江区(district) → 测试小学(SCH001) → 三年级一班(CLS001) → 小明(student)
```

以及：4 道已审核客观题、一张已发布试卷「三年级音乐正式测评」（formal，总分 20，scope=class）。

### 1.3 启动服务

```bash
python manage.py runserver 8000
```

### 1.4 账号速查表

| 账号 | 密码 | 角色 | 用途 |
| --- | --- | --- | --- |
| `student` | `student123456` | 学生 | 作答、看成绩、证书 |
| `teacher` | `teacher123456` | 教师 | 评分、查看/导出学生、学生证书 |
| `school` | `school123456` | 学校管理员 | 统计、评分、补录 |
| `district` | `district123456` | 区县管理员 | 统计、补录 |
| `city` | `city123456` | 市州管理员 | 统计、补录 |
| `province` | `province123456` | 省级管理员 | 统计、参与率导出 |
| `admin` | `admin123456` | 超级用户 | 全部接口（兜底排查） |

---

## 二、把接口导入 Apifox

1. Apifox →「导入数据」→「OpenAPI / Swagger」→ 选择 `docs/api/openapi-c.yaml`。
2. 自动生成分组：**认证 / 测评作答 / 判分与评分 / 学生端结果 / 数据统计 / 证书**（28 个请求）。

---

## 三、环境与认证（多角色切换是核心）

### 3.1 统一响应信封

所有接口的 HTTP 响应都包在统一信封里：

```json
{
  "code": 0,           // 0=成功，非0=业务错误
  "message": "ok",     // 提示语
  "data": { ... }      // 真正的业务数据（下面每个接口的「响应」都指这里的内容）
}
```

错误时：`{ "code": <非0>, "message": "错误描述", "data": null }`（部分接口附带 `detail` 与 `code` 错误码）。

### 3.2 建环境

1. Apifox「环境管理」→ 新建环境 `本地-dev`：
   - `baseUrl` = `http://127.0.0.1:8000`
   - `access` = （留空）
2. 全局 Header 加一条：`Authorization: Bearer {{access}}`。

### 3.3 登录拿 token

- **接口名**：登录并获取 JWT
- `POST {{baseUrl}}/api/auth/login/`

请求体：

```json
{ "username": "student", "password": "student123456" }
```

响应（token 在 `data.access`）：

```json
{
  "code": 0,
  "message": "ok",
  "data": { "refresh": "eyJ...refresh", "access": "eyJ...access" }
}
```

**后置操作**：提取变量 `$.data.access` → 写入环境变量 `access`。

### 3.4 多角色切换

换角色 = 换账号登录 = 重新提取 `access`：
- 测「作答/学生端/证书(学生)」→ 登录 `student`
- 测「评分/学生证书(教师)」→ 登录 `teacher`
- 测「统计」→ 分别登录 `school`/`district`/`city`/`province` 验证不同层级

> 建议建多个环境（`本地-学生`、`本地-教师`、`本地-管理员`）各自缓存 token，切换环境即切换身份。

---

## 四、分链路逐步测试（每步含完整 JSON）

> 文件下载类接口（xlsx/html/zip）需在 Apifox 勾选「保存响应到文件」，否则看到乱码。

---

### 链路 A：学生作答（`student` 账号）

**前置**：登录 `student`，提取 token。

#### A1 · #1 我可作答的测评列表

- **接口名**：我可作答的测评列表
- `GET {{baseUrl}}/api/exam/my-assessments/`
- **角色**：学生

**请求参数**：无

**响应 200**（`data` 字段，列表接口为分页结构）：

```json
{
  "list": [
    {
      "id": 1,                  // ← publish_id，下面 #2/#3 用
      "paper_id": 1,
      "title": "三年级音乐正式测评",
      "subject": "music",
      "subject_display": "音乐",
      "ptype": "formal",
      "ptype_display": "正式测评",
      "grade": "三年级",
      "duration": 30,
      "total_score": "20",
      "question_count": 4,
      "start_at": null,
      "end_at": null,
      "sheet_id": null,         // 未开始作答为 null
      "is_submitted": false,
      "my_score": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

**验证**：`list` 里有「三年级音乐正式测评」，记下 `id`（= publish_id，下面用 `{pid}`）。

#### A2 · #2 试卷详情（拿题目）

- **接口名**：试卷详情（含题目与音视频资源）
- `GET {{baseUrl}}/api/exam/my-assessments/{pid}/`
- **角色**：学生

**请求参数**：路径参数 `id`（publish_id）

**响应 200**（`data`）：

```json
{
  "id": 1,
  "paper": {
    "id": 1,
    "title": "三年级音乐正式测评",
    "subject": "music",
    "subject_display": "音乐",
    "ptype": "formal",
    "ptype_display": "正式测评",
    "grade": "三年级",
    "duration": 30,
    "total_score": "20",
    "question_count": 4
  },
  "start_at": null,
  "end_at": null,
  "is_open": true,
  "questions": [
    {
      "id": 1,                 // ← question_id，下面 #4 用
      "sort": 1,
      "qtype": "single",
      "qtype_display": "单选题",
      "difficulty": "easy",
      "grade": "三年级",
      "stem": "以下哪个是高音谱号？",
      "options": [ { "key": "A", "text": "𝄞" }, { "key": "B", "text": "𝄢" } ],
      "score": "5",
      "resources": []
    }
  ],
  "sheet": null,
  "my_answers": []
}
```

**验证**：`questions` 是 4 道题，记下每道 `id`（question_id）。**提交前 `answer`（参考答案）字段不返回**。

#### A3 · #3 开始作答（创建答卷）

- **接口名**：开始作答（创建答卷）
- `POST {{baseUrl}}/api/exam/answer-sheets/`
- **角色**：学生

请求体（`publish_id` / `paper_id` 二选一）：

```json
{ "publish_id": 1 }
```

**响应 201**（`data`）：

```json
{
  "id": 1,                    // ← sheet_id，下面 #4/#5 用
  "paper_id": 1,
  "publish_id": 1,
  "started_at": "2026-10-22T19:56:00+08:00",
  "submitted_at": null,
  "is_submitted": false,
  "total_score": "0"
}
```

**验证**：记下 `id`（sheet_id，下面用 `{sid}`）。重复调用同一 `publish_id` 返回同一份答卷。

#### A4 · #4 保存答题进度

- **接口名**：保存答题进度
- `PUT {{baseUrl}}/api/exam/answer-sheets/{sid}/answers/`
- **角色**：学生

请求体：

```json
{
  "answers": [
    { "question_id": 1, "answer": "A" },
    { "question_id": 2, "answer": "B" },
    { "question_id": 3, "answer": "ACD" },
    { "question_id": 4, "answer": "正确" }
  ]
}
```

**响应 200**（`data`）：

```json
{ "sheet_id": 1, "saved": 4, "is_submitted": false }
```

**验证**：`saved` = 你提交的题数。正确答案见「六、关键参数速查」。

#### A5 · #5 提交答卷（自动判分）

- **接口名**：提交答卷（自动判分）
- `POST {{baseUrl}}/api/exam/answer-sheets/{sid}/submit/`
- **角色**：学生

**请求体**：无

**响应 200**（`data`）：

```json
{
  "id": 1,
  "paper_id": 1,
  "publish_id": 1,
  "started_at": "2026-10-22T19:56:00+08:00",
  "submitted_at": "2026-10-22T19:58:00+08:00",
  "is_submitted": true,
  "total_score": "20",
  "paper_total_score": "20",
  "correct_count": 4,
  "wrong_count": 0,
  "subjective_pending": 0,
  "pass": true
}
```

**验证**：4 题全对 → `total_score: "20"`、`correct_count: 4`、`pass: true`（≥ 60% 即 12 分为通过）。

#### A6 · #13 测评记录

- **接口名**：测评记录列表
- `GET {{baseUrl}}/api/exam/my-assessments/records/`
- **角色**：学生

**响应 200**（`data.list` 元素）：

```json
{
  "sheet_id": 1,
  "publish_id": 1,
  "paper_id": 1,
  "title": "三年级音乐正式测评",
  "subject": "music",
  "subject_display": "音乐",
  "ptype": "formal",
  "ptype_display": "正式测评",
  "total_score": "20",
  "my_score": "20",
  "is_submitted": true,
  "started_at": "2026-10-22T19:56:00+08:00",
  "submitted_at": "2026-10-22T19:58:00+08:00"
}
```

#### A7 · #12 统计分析报告

- **接口名**：测评统计分析报告
- `GET {{baseUrl}}/api/exam/my-assessments/{pid}/report/`
- **角色**：学生（需已提交答卷）

**响应 200**（`data`）：

```json
{
  "sheet_id": 1,
  "publish_id": 1,
  "paper_title": "三年级音乐正式测评",
  "subject": "music",
  "subject_display": "音乐",
  "ptype": "formal",
  "total_score": "20",
  "my_score": "20",
  "correct_rate": 1.0,
  "score_rate": 1.0,
  "correct_count": 4,
  "wrong_count": 0,
  "subjective_count": 0,
  "question_count": 4,
  "class_average": "20.00",
  "class_size": 1,
  "submitted_at": "2026-10-22T19:58:00+08:00",
  "details": [
    {
      "question_id": 1,
      "sort": 1,
      "qtype": "single",
      "qtype_display": "单选题",
      "stem": "以下哪个是高音谱号？",
      "my_answer": "A",
      "correct_answer": "A",
      "analysis": "",
      "full_score": "5",
      "score": "5",
      "is_correct": true
    }
  ]
}
```

**验证**：提交后 `details` 会带参考答案与解析。

---

### 链路 B：学生端结果（`student` 账号，紧接链路 A）

#### B1 · #14 我的成绩

- **接口名**：查看我的成绩
- `GET {{baseUrl}}/api/exam/my-scores/`
- **角色**：学生

**响应 200**（`data`）：

```json
{
  "exams": [
    {
      "source": "exam",
      "title": "三年级音乐正式测评",
      "subject": "music",
      "subject_display": "音乐",
      "ptype": "formal",
      "score": 20.0,
      "total_score": 20.0,
      "rate": 1.0,
      "date": "2026-10-22 19:58:00"
    }
  ],
  "performances": [
    {
      "source": "daily",
      "title": "音乐评分",
      "subject": "music",
      "subject_display": "音乐",
      "ptype": "daily",
      "score": 88.0,
      "total_score": 100.0,
      "rate": 0.88,
      "date": "2026-10-22 20:00:00"
    }
  ],
  "by_subject": [
    { "subject": "music", "subject_display": "音乐", "count": 2, "average_rate": 0.94 }
  ]
}
```

**验证**：`exams` 有测评成绩；`performances` 是平时表现评分（教师评分后才出现）；`by_subject` 有学科均分。

#### B2 · #15 成绩曲线

- **接口名**：成绩曲线
- `GET {{baseUrl}}/api/exam/my-scores/curve/`
- **角色**：学生

**请求参数**（可选）：`?subject=music`

**响应 200**（`data`）：

```json
{
  "points": [
    {
      "source": "exam",
      "title": "三年级音乐正式测评",
      "subject": "music",
      "subject_display": "音乐",
      "ptype": "formal",
      "score": 20.0,
      "total_score": 20.0,
      "rate": 1.0,
      "date": "2026-10-22 19:58:00"
    }
  ],
  "total": 1
}
```

#### B3 · #16 成长曲线（音乐/美术）

- **接口名**：个人成长曲线
- `GET {{baseUrl}}/api/exam/my-growth/`
- **角色**：学生

**响应 200**（`data`）：

```json
{
  "series": [
    {
      "subject": "music",
      "subject_display": "音乐",
      "count": 2,
      "average_rate": 0.94,
      "points": [ { "...": "同 #15 的 point 结构" } ]
    }
  ],
  "total": 2
}
```

#### B4 · #17 上传课外学习图片

- **接口名**：上传课外自主学习图片
- `POST {{baseUrl}}/api/exam/extracurricular/`
- **角色**：学生
- **请求类型**：`multipart/form-data`

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `image` | file | 是 | 任意图片 |
| `title` | text | 否 | 标题 |
| `description` | text | 否 | 说明 |

**响应 201**（`data`）：

```json
{
  "id": 1,
  "title": "课外学习成果",
  "image": "http://127.0.0.1:8000/media/extracurricular/2026/10/xxx.png",
  "description": "",
  "created_at": "2026-10-22T20:00:00+08:00"
}
```

---

### 链路 C：判分与评分（`teacher` 账号）

**前置**：登录 `teacher`，重新提取 token。记下学生 id（`{sid}`，获取方式见「六」）。

#### C1 · #6 查看学生课外材料

- **接口名**：查看学生课外学习材料
- `GET {{baseUrl}}/api/exam/students/{sid}/extracurricular/`
- **角色**：教师 / 学校

**响应 200**（`data`）：

```json
{
  "student_id": 4,
  "list": [
    {
      "id": 1,
      "title": "课外学习成果",
      "description": "",
      "image": "http://127.0.0.1:8000/media/extracurricular/2026/10/xxx.png",
      "created_at": "2026-10-22T20:00:00+08:00"
    }
  ],
  "total": 1
}
```

**验证**：能看到 B4 上传的图片，说明「学生上传 → 教师可见」链路通。

#### C2 · #7 查看学生测评成绩

- **接口名**：查看学生测评成绩
- `GET {{baseUrl}}/api/exam/students/{sid}/scores/`
- **角色**：教师 / 学校

**响应 200**（`data`）：

```json
{
  "student": {
    "id": 4,
    "username": "student",
    "real_name": "小明",
    "student_no": "S2024001"
  },
  "exams": [
    {
      "sheet_id": 1,
      "paper_id": 1,
      "title": "三年级音乐正式测评",
      "subject": "music",
      "subject_display": "音乐",
      "ptype": "formal",
      "score": 20.0,
      "total_score": 20.0,
      "submitted_at": "2026-10-22T19:58:00+08:00"
    }
  ],
  "performances": [
    {
      "id": 1,
      "course": "音乐",
      "klass": "三年级一班",
      "score": 88.0,
      "comment": "课堂表现积极",
      "scorer": "李老师",
      "created_at": "2026-10-22T20:00:00+08:00"
    }
  ],
  "subject_average": { "音乐": 20.0 }
}
```

#### C3 · #8 为学生平时表现评分

- **接口名**：为学生平时表现评分
- `POST {{baseUrl}}/api/exam/students/{sid}/scores/daily/`
- **角色**：教师 / 学校

请求体：

```json
{ "score": 88, "course_id": 1, "klass_id": 1, "comment": "课堂表现积极" }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `score` | number | 是 | 0-100 |
| `course_id` | number | 否 | 学科（音乐/美术） |
| `klass_id` | number | 否 | 班级 |
| `comment` | string | 否 | 评语 |

**响应 200**（`data`）：

```json
{ "id": 1, "student_id": 4, "score": 88.0, "course": "音乐", "comment": "课堂表现积极" }
```

**验证**：回到 B1「我的成绩」，`performances` 会出现这条。

#### C4 · #9 成绩导入模板下载

- **接口名**：成绩导入模板下载
- `GET {{baseUrl}}/api/exam/scores/template/`
- **角色**：教师 / 学校

**响应**：xlsx 文件（表头「学籍号/姓名/班级编号/学科/分数/评语」，含 2 行示例）。勾选「保存响应到文件」。

#### C5 · #10 导入学生线下成绩

- **接口名**：导入学生线下成绩
- `POST {{baseUrl}}/api/exam/scores/import/`
- **角色**：教师 / 学校
- **请求类型**：`multipart/form-data`，字段 `file`

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | xlsx（用 C4 模板，列顺序：学籍号/姓名/班级编号/学科/分数/评语） |

**响应 200**（`data`）：

```json
{ "total": 1, "success": 1, "failed": 0, "errors": [] }
```

#### C6 · #11 测评成绩补录

- **接口名**：测评成绩补录
- `POST {{baseUrl}}/api/exam/scores/supplement/`
- **角色**：学校 / 区县 / 市州（教师 403）

请求体：

```json
{
  "items": [
    { "student_no": "S2024001", "score": 90, "course_id": 1, "klass_id": 1, "comment": "线下测评补录" }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `student_no` / `student_id` | string / number | 二选一 | 定位学生 |
| `score` | number | 是 | 0-100 |
| `course_id` / `klass_id` / `comment` | — | 否 | 可选 |

**响应 200**（`data`）：

```json
{
  "success": 1,
  "failed": 0,
  "results": [ { "id": 1, "student_id": 4, "student_no": "S2024001", "score": 90.0 } ],
  "errors": []
}
```

#### C7 · #21 导出学生所有成绩

- **接口名**：导出学生所有成绩
- `GET {{baseUrl}}/api/exam/students/{sid}/scores/export/`
- **角色**：教师 / 学校

**响应**：xlsx 文件（表头「类型/名称/学科/得分/满分/时间/评语」，含测评+平时表现两类行）。勾选「保存响应到文件」。

---

### 链路 D：数据统计（`school`/`district`/`city`/`province` 账号）

**前置**：先有学生提交答卷（链路 A 已产生）。登录 `school`（或更高层级）提取 token。

#### D1 · #18 测评数据统计

- **接口名**：测评数据统计
- `GET {{baseUrl}}/api/exam/stats/assessment/`
- **角色**：学校 / 区县 / 市州 / 省级

**请求参数**（可选）：`school_id`、`region_id`、`grade`、`subject`、`ptype`

**响应 200**（`data`）：

```json
{
  "summary": {
    "student_total": 1,
    "participant_count": 1,
    "submission_count": 1,
    "participation_rate": 1.0,
    "average_score_rate": 1.0,
    "pass_rate": 1.0
  },
  "by_subject": [
    { "key": "music", "label": "音乐", "participant_count": 1, "submission_count": 1, "average_score_rate": 1.0, "pass_rate": 1.0 }
  ],
  "by_grade": [
    { "key": "三年级", "label": "三年级", "participant_count": 1, "submission_count": 1, "average_score_rate": 1.0, "pass_rate": 1.0 }
  ],
  "by_school": [
    { "key": "测试小学", "label": "测试小学", "participant_count": 1, "submission_count": 1, "average_score_rate": 1.0, "pass_rate": 1.0 }
  ]
}
```

#### D2 · #19 统计导出 Excel

- **接口名**：统计导出 Excel
- `GET {{baseUrl}}/api/exam/stats/assessment/export/`
- **角色**：学校 / 区县 / 市州 / 省级

**响应**：xlsx「测评数据统计.xlsx」。勾选「保存响应到文件」。

#### D3 · #20 测评参与率导出

- **接口名**：测评参与率导出（省级）
- `GET {{baseUrl}}/api/exam/stats/participation/export/`
- **角色**：仅省级

**请求参数**（可选）：`region_id`

**响应**：xlsx「测评参与率.xlsx」（表头「市州/区县/学校/学生数/参与人数/参与率」）。
**负向验证**：用 `teacher` 调此接口 → 403。

---

### 链路 E：证书（`student` + `teacher` 账号）

**前置**：证书在「正式测评提交且得分率 ≥ 60%」时自动发放（链路 A 全对或答对 3 题即可）。

#### E1 · #22 我的证书列表

- **接口名**：我的证书列表
- `GET {{baseUrl}}/api/exam/certificates/`
- **角色**：学生

**响应 200**（`data.list` 元素）：

```json
{
  "id": 1,                     // ← certificate id，下面 #23/#24 用
  "title": "音乐正式测评证书",
  "subject": "music",
  "subject_display": "音乐",
  "student_id": 4,
  "student_name": "小明",
  "sheet_id": 1,
  "score": 20.0,
  "file": "",
  "created_at": "2026-10-22T19:58:00+08:00"
}
```

#### E2 · #23 证书详情

- **接口名**：证书详情
- `GET {{baseUrl}}/api/exam/certificates/{cid}/`
- **角色**：学生

**响应 200**（`data`）：同 #22 的单条证书结构。

#### E3 · #24 下载证书

- **接口名**：下载证书
- `GET {{baseUrl}}/api/exam/certificates/{cid}/download/`
- **角色**：学生

**响应**：HTML 证书文件（无附件时自动按模板生成）。勾选「保存响应到文件」，浏览器打开可见姓名与成绩。

#### E4 · #25 查看学生证书（教师）

- **接口名**：查看学生证书
- `GET {{baseUrl}}/api/exam/students/{sid}/certificates/`
- **角色**：教师 / 学校

**响应 200**（`data`）：

```json
{
  "student_id": 4,
  "list": [ { "同 #22 单条证书结构" } ],
  "total": 1
}
```

#### E5 · #26 导出学生证书（教师）

- **接口名**：导出学生证书
- `GET {{baseUrl}}/api/exam/students/{sid}/certificates/export/`
- **角色**：教师 / 学校

**响应**：xlsx「小明_证书.xlsx」（表头「证书编号/证书名称/学科/关联测评/成绩/颁发时间」）。勾选「保存响应到文件」。

---

## 五、负向 / 权限验证（可选但建议做）

| 验证项 | 做法 | 预期 |
| --- | --- | --- |
| 学生访问教师接口 | `student` 调 `/api/exam/students/{sid}/scores/` | 403 |
| 教师访问学生「我可作答」 | `teacher` 调 `/api/exam/my-assessments/` | 403 |
| 教师访问统计 | `teacher` 调 `/api/exam/stats/assessment/` | 403 |
| 教师访问参与率导出 | `teacher` 调 `/api/exam/stats/participation/export/` | 403（仅省级） |
| 未提交就看报告 | `student` 提交前调 `.../report/` | 400（答卷尚未提交） |
| 提交后重复作答 | 对已提交 `publish_id` 再调「开始作答」 | 409（已提交，不能重新作答） |

---

## 六、关键参数速查

### 6.1 seed 的 4 道题及正确答案（用于 A4 保存进度）

| 题号 | 题型 | 题干关键词 | 正确答案 |
| --- | --- | --- | --- |
| 1 | single | 高音谱号 | `A` |
| 2 | single | 四分音符时值 | `B` |
| 3 | multiple | 西洋乐器 | `ACD`（三字母连写，**不要加逗号**） |
| 4 | judge | a1 频率 440Hz | `正确` |

> ⚠️ 多选题判分按「去空格去分隔符后的字母集合」比对，直接写 `ACD`，不要写 `A,C,D`。

### 6.2 怎么拿 `student_id`（教师接口要用）

1. 登录 `student` → `GET /api/users/me/` → 响应 `data.id` 即学生 id。
2. seed 不保证固定 id（取决于库里既有数据）；**以 `/api/users/me/` 返回为准**。

> 参考：当前开发库中 `student` 的 id 是 **4**（库里已存在 reset_a_data 的旧账号占用了 1-3）。

### 6.3 音乐课程 id

登录 `admin` → `GET /api/questionbank/courses/` 查「音乐」的 id。C3 平时评分 `course_id` 传它（也可不传）。

### 6.4 及格线与证书规则

- 及格线 = **60%**（`PASS_RATIO = 0.6`）。
- 只有 `ptype = formal`（正式测评）且得分率 ≥ 60% 才自动发证书；`practice`（练习）不发证。
- 想验证「不及格不发证」：A4 只答对 2 题（10/20 = 50%），提交后 E1 列表无新证书。

---

## 七、常见问题排查

| 现象 | 原因与解决 |
| --- | --- |
| 启动报 `no such column: ..._deleted_at` | 迁移冲突/未迁移，回看「1.1」执行 `makemigrations --merge --noinput` + `migrate` |
| 学生「我可作答」列表为空 | 学生没在已审核班级 / 发布 scope 不匹配 / 时间窗口未到。重跑 `seed_demo` |
| 登录后请求 401 | token 没提取对。取的是 `data.access`，Header 是 `Authorization: Bearer {{access}}` |
| 403 Forbidden | 角色不对。核对当前登录账号是否属于该接口允许角色 |
| 列表接口结构对不上 | 列表统一是 `data.list` + `data.total`，不是 DRF 的 `results/count` |
| 文件接口乱码 | 下载类接口勾选「保存响应到文件」 |
| 多选题被判错 | 答案格式问题，见「6.1」直接写 `ACD` |

---

## 附：完整接口路径速查

| # | 方法 | 路径 | 角色 |
| --- | --- | --- | --- |
| 1 | GET | `/api/exam/my-assessments/` | 学生 |
| 2 | GET | `/api/exam/my-assessments/{id}/` | 学生 |
| 3 | POST | `/api/exam/answer-sheets/` | 学生 |
| 4 | PUT | `/api/exam/answer-sheets/{id}/answers/` | 学生 |
| 5 | POST | `/api/exam/answer-sheets/{id}/submit/` | 学生 |
| 12 | GET | `/api/exam/my-assessments/{id}/report/` | 学生 |
| 13 | GET | `/api/exam/my-assessments/records/` | 学生 |
| 6 | GET | `/api/exam/students/{sid}/extracurricular/` | 教师/学校 |
| 7 | GET | `/api/exam/students/{sid}/scores/` | 教师/学校 |
| 8 | POST | `/api/exam/students/{sid}/scores/daily/` | 教师/学校 |
| 9 | GET | `/api/exam/scores/template/` | 教师/学校 |
| 10 | POST | `/api/exam/scores/import/` | 教师/学校 |
| 11 | POST | `/api/exam/scores/supplement/` | 学校/区县/市州 |
| 21 | GET | `/api/exam/students/{sid}/scores/export/` | 教师/学校 |
| 14 | GET | `/api/exam/my-scores/` | 学生 |
| 15 | GET | `/api/exam/my-scores/curve/` | 学生 |
| 16 | GET | `/api/exam/my-growth/` | 学生 |
| 17 | POST | `/api/exam/extracurricular/` | 学生 |
| 18 | GET | `/api/exam/stats/assessment/` | 学校/区县/市州/省级 |
| 19 | GET | `/api/exam/stats/assessment/export/` | 学校/区县/市州/省级 |
| 20 | GET | `/api/exam/stats/participation/export/` | 仅省级 |
| 22 | GET | `/api/exam/certificates/` | 学生 |
| 23 | GET | `/api/exam/certificates/{id}/` | 学生 |
| 24 | GET | `/api/exam/certificates/{id}/download/` | 学生 |
| 25 | GET | `/api/exam/students/{sid}/certificates/` | 教师/学校 |
| 26 | GET | `/api/exam/students/{sid}/certificates/export/` | 教师/学校 |
