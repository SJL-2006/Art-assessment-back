# B 模块（题库 · 试卷）Apifox 测试文档

> 适用对象：负责验收成员 B 交付的题库（课程/章节/试题/资源/审核）与试卷（组卷/暂存/发布/下载）接口。
> 每个接口都给出 **接口名、方法/路径、角色、请求 JSON、响应 JSON 字段**，按「准备 → 导入 → 认证 → 分链路逐步测试」顺序操作即可。

---

## 〇、接口总览

B 模块共 **5 组资源**，接口如下（含 2 个 A 域复用的认证接口）：

| 组 | 资源 | 接口 | 调用角色 |
| --- | --- | --- | --- |
| 认证 | JWT | #1-#2 | 公开 |
| 题库 | 课程 Course | #3-#7 | 读：学生/教师/题库管理员；写：仅题库管理员 |
| 题库 | 章节 Chapter | #8-#12 | 同上 |
| 题库 | 试题 Question | #13-#22 | 教师/题库管理员；审核仅题库管理员 |
| 试卷 | 试卷 Paper | #23-#30 | 教师/学校/区县/市州/省级 |
| 试卷 | 试题关联 PaperQuestion | #31-#35 | 教师/学校/区县/市州/省级 |
| 试卷 | 发布 PaperPublish | #36-#41 | 教师/学校/区县/市州/省级 |

> 数据依赖：B 模块的题库（课程/试题）是 A 模块「组织/账号」之上的资源；试卷又依赖题库。先有 admin 建课程→建题→审核，再由 teacher 组卷→发布，学生才能作答（C 模块）。

---

## 一、前置准备

### 1.1 迁移 + 演示数据

```bash
python manage.py makemigrations --merge --noinput
python manage.py migrate
python manage.py seed_demo
```

`seed_demo` 已为 B 模块备好：课程「音乐/美术」、4 道已审核客观题、一张已发布试卷「三年级音乐正式测评」（formal，总分 20，scope=class）。可直接拿这些数据联调，也可自己新建数据走完整流程。

### 1.2 启动服务

```bash
python manage.py runserver 8000
```

### 1.3 账号速查

| 账号 | 密码 | 角色 | 适合测 |
| --- | --- | --- | --- |
| `admin` | `admin123456` | 题库管理员(超管) | 题库全部写操作、审核、兜底 |
| `teacher` | `teacher123456` | 教师 | 试题写、试卷全部操作 |
| `student` | `student123456` | 学生 | 仅查看课程/章节（不可写题） |
| `school` | `school123456` | 学校管理员 | 试卷读 |

---

## 二、把接口导入 Apifox

1. Apifox →「导入数据」→「OpenAPI / Swagger」→ 选择 `docs/schema.yml`。
2. 分组：题库（课程/章节/试题）、试卷（试卷/试题关联/发布）。

> 不同步时：`python manage.py spectacular --file docs/schema.yml` 重新生成；或浏览器打开 `http://127.0.0.1:8000/api/docs/`。

---

## 三、环境与认证

统一信封：`{ "code": 0, "message": "ok", "data": {...} }`；错误：`{ "code": <非0>, "message": "...", "data": null }`。

1. 环境变量：`baseUrl` = `http://127.0.0.1:8000`、`access` = 空。
2. 全局 Header：`Authorization: Bearer {{access}}`。
3. 登录 `POST {{baseUrl}}/api/auth/login/`，后置提取 `$.data.access`。

> 建议：`admin` 登录存一个环境（测题库写操作/审核），`teacher` 登录存一个环境（测试卷组卷/发布）。

---

## 四、分链路逐步测试（每步含完整 JSON）

> 公共字段说明：继承 BaseModel 的资源（课程/章节/试题/试卷/发布等）响应都会额外带 `id`、`created_at`、`updated_at`、`is_deleted`、`deleted_at` 这 5 个公共字段，下面 JSON 不逐个重复，首次出现处列出。

---

### 链路 A：认证（公开）

#### A1 · #1 登录

- **接口名**：登录并获取 JWT
- `POST {{baseUrl}}/api/auth/login/`
- **角色**：公开

请求体：

```json
{ "username": "admin", "password": "admin123456" }
```

响应 200（`data`）：

```json
{ "refresh": "eyJ...", "access": "eyJ..." }
```

#### A2 · #2 刷新令牌

- **接口名**：刷新访问令牌
- `POST {{baseUrl}}/api/auth/refresh/`
- **角色**：公开

请求体：

```json
{ "refresh": "eyJ...refresh" }
```

响应 200（`data`）：

```json
{ "access": "eyJ...new", "refresh": "eyJ...new" }
```

---

### 链路 B：题库 - 课程（Course）

#### B1 · #3-#7 课程 CRUD

- **接口名**：课程 列表 / 新增 / 详情 / 修改 / 删除

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/questionbank/courses/` | 学生/教师/题库管理员 |
| POST | `/api/questionbank/courses/` | 仅题库管理员 |
| GET | `/api/questionbank/courses/{id}/` | 学生/教师/题库管理员 |
| PUT | `/api/questionbank/courses/{id}/` | 仅题库管理员 |
| DELETE | `/api/questionbank/courses/{id}/` | 仅题库管理员 |

请求体（POST/PUT）：

```json
{ "name": "舞蹈", "code": "dance", "description": "舞蹈课程" }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 课程名（唯一） |
| `code` | string | 否 | 课程编码 |
| `description` | string | 否 | 描述 |

**响应**（`data`，单条 Course）：

```json
{
  "id": 3,
  "name": "舞蹈",
  "code": "dance",
  "description": "舞蹈课程",
  "created_at": "2026-10-22T20:00:00+08:00",
  "updated_at": "2026-10-22T20:00:00+08:00",
  "is_deleted": false,
  "deleted_at": null
}
```

**负向验证**：`teacher` 调 POST → 403（仅题库管理员）。

---

### 链路 C：题库 - 章节（Chapter）

#### C1 · #8-#12 章节 CRUD

- **接口名**：章节 列表 / 新增 / 详情 / 修改 / 删除

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/questionbank/chapters/` | 学生/教师/题库管理员 |
| POST | `/api/questionbank/chapters/` | 仅题库管理员 |
| GET | `/api/questionbank/chapters/{id}/` | 学生/教师/题库管理员 |
| PUT | `/api/questionbank/chapters/{id}/` | 仅题库管理员 |
| DELETE | `/api/questionbank/chapters/{id}/` | 仅题库管理员 |

请求体（POST/PUT）：

```json
{ "course": 1, "name": "乐理基础", "parent": null, "sort": 1 }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `course` | number | 是 | 所属课程 id |
| `name` | string | 是 | 章节名 |
| `parent` | number | 否 | 父章节 id（可两级） |
| `sort` | number | 否 | 排序值 |

**响应**（`data`，单条 Chapter）：

```json
{ "id": 1, "course": 1, "name": "乐理基础", "parent": null, "sort": 1 }
```

列表查询参数：`?course=1`。

---

### 链路 D：题库 - 试题（Question）

#### D1 · #13-#17 试题 CRUD

- **接口名**：试题 列表 / 新增 / 详情 / 修改 / 删除

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/questionbank/questions/` | 教师/题库管理员 |
| POST | `/api/questionbank/questions/` | 教师/题库管理员 |
| GET | `/api/questionbank/questions/{id}/` | 教师/题库管理员 |
| PUT | `/api/questionbank/questions/{id}/` | 教师/题库管理员 |
| DELETE | `/api/questionbank/questions/{id}/` | 教师/题库管理员 |

请求体（POST，示例：单选题）：

```json
{
  "course": 1,
  "chapter": 1,
  "qtype": "single",
  "difficulty": "easy",
  "grade": "三年级",
  "stem": "五线谱有几条线？",
  "options": [ { "key": "A", "text": "3条" }, { "key": "B", "text": "5条" }, { "key": "C", "text": "7条" } ],
  "answer": "B",
  "analysis": "五线谱由五条平行横线组成。",
  "score": 5,
  "status": "draft"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `course` | number | 是 | 课程 id |
| `chapter` | number | 否 | 章节 id |
| `qtype` | string | 是 | single/multiple/judge/fill/short/listening/sight |
| `difficulty` | string | 否 | easy/medium/hard |
| `grade` | string | 否 | 适用年级 |
| `stem` | string | 是 | 题干 |
| `options` | array | 否 | 选项数组 `[{key,text}]`（判断题可为空） |
| `answer` | string | 是 | 答案（多选如 "ACD"，判断填 "正确"/"错误"） |
| `analysis` | string | 否 | 解析 |
| `score` | number | 否 | 分值 |
| `status` | string | 否 | draft/pending/approved/rejected，默认 draft |

**响应**（`data`，单条 Question，含嵌套资源与冗余名）：

```json
{
  "id": 5,
  "course": 1,
  "chapter": 1,
  "qtype": "single",
  "difficulty": "easy",
  "grade": "三年级",
  "stem": "五线谱有几条线？",
  "options": [ { "key": "A", "text": "3条" }, { "key": "B", "text": "5条" }, { "key": "C", "text": "7条" } ],
  "answer": "B",
  "analysis": "五线谱由五条平行横线组成。",
  "score": 5,
  "status": "draft",
  "creator": 1,
  "reviewer": null,
  "resources": [],
  "course_name": "音乐",
  "chapter_name": "乐理基础"
}
```

列表查询参数：`?course=1`、`?qtype=single`、`?difficulty=easy`、`?grade=三年级`、`?status=approved`。

#### D2 · #18 上传试题资源

- **接口名**：上传试题资源（音频/图片/视频）
- `POST {{baseUrl}}/api/questionbank/questions/{id}/resources/`
- **角色**：教师/题库管理员

**请求**：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `rtype` | string | 是 | audio/image/video |
| `file` | file | 是 | 上传的文件 |

**响应 201**（`data`，QuestionResource）：

```json
{
  "id": 1,
  "question": 5,
  "rtype": "audio",
  "file": "/media/question_resources/xxx.mp3"
}
```

#### D3 · #19 删除试题资源

- **接口名**：删除试题资源
- `DELETE {{baseUrl}}/api/questionbank/questions/{id}/resources/{rid}/`
- **角色**：教师/题库管理员

**响应 200**：`{ "code": 0, "message": "删除成功", "data": null }`。

#### D4 · #20 审核试题

- **接口名**：审核试题
- `POST {{baseUrl}}/api/questionbank/questions/{id}/review/`
- **角色**：仅题库管理员

请求体：

```json
{ "result": "approved", "comment": "答案无误" }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `result` | string | 是 | approved / rejected |
| `comment` | string | 否 | 审核意见 |

**响应 201**（`data`，QuestionReview）：

```json
{ "id": 1, "question": 5, "reviewer": 1, "result": "approved", "comment": "答案无误" }
```

> 审核通过后，试题 `status` 自动变为 `approved`（可被组卷引用）。

#### D5 · #21 查看审核记录

- **接口名**：试题审核记录列表
- `GET {{baseUrl}}/api/questionbank/questions/{id}/reviews/`
- **角色**：仅题库管理员

**响应 200**（`data.list` 元素同 D4）。

---

### 链路 E：试卷 - 组卷（Paper）

#### E1 · #22-#26 试卷 CRUD

- **接口名**：试卷 列表 / 新增 / 详情 / 修改 / 删除

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/exam/papers/` | 教师/学校/区县/市州/省级 |
| POST | `/api/exam/papers/` | 教师/学校/区县/市州/省级 |
| GET | `/api/exam/papers/{id}/` | 教师/学校/区县/市州/省级 |
| PUT | `/api/exam/papers/{id}/` | 教师/学校/区县/市州/省级 |
| DELETE | `/api/exam/papers/{id}/` | 教师/学校/区县/市州/省级 |

请求体（POST，手工建卷）：

```json
{
  "title": "三年级音乐随堂练习",
  "ptype": "practice",
  "subject": "music",
  "level": "class",
  "grade": "三年级",
  "duration": 20,
  "total_score": 10,
  "status": "draft"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 试卷标题 |
| `subject` | string | 是 | 科目（music/art/…） |
| `ptype` | string | 否 | practice(练习)/formal(正式测评)，默认 practice |
| `level` | string | 否 | class/school/region，默认 class |
| `grade` | string | 否 | 年级 |
| `duration` | number | 否 | 时长（分钟） |
| `total_score` | number | 否 | 总分 |
| `status` | string | 否 | draft/published，默认 draft |

**响应**（`data`，单条 Paper，含 `question_count`）：

```json
{
  "id": 2,
  "title": "三年级音乐随堂练习",
  "ptype": "practice",
  "subject": "music",
  "level": "class",
  "grade": "三年级",
  "duration": 20,
  "total_score": 10,
  "status": "draft",
  "creator": 2,
  "question_count": 0
}
```

#### E2 · #27 自动组卷

- **接口名**：按配置自动组卷
- `POST {{baseUrl}}/api/exam/papers/auto-generate/`
- **角色**：教师/学校/区县/市州/省级

请求体：

```json
{
  "title": "三年级音乐自动组卷",
  "subject": "music",
  "grade": "三年级",
  "chapter_ids": [1],
  "qtype_config": [
    { "qtype": "single", "count": 2, "difficulty": "easy" },
    { "qtype": "multiple", "count": 1, "difficulty": "easy" },
    { "qtype": "judge", "count": 1, "difficulty": "easy" }
  ],
  "total_score": 20,
  "ptype": "formal",
  "level": "class"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 试卷标题 |
| `subject` | string | 是 | 科目 |
| `grade` | string | 否 | 年级 |
| `chapter_ids` | array | 否 | 限定章节范围 |
| `qtype_config` | array | 是 | 组卷规则，元素 `{qtype,count,difficulty}`，非空 |
| `total_score` | number | 否 | 总分（不传按各题分值累加） |
| `ptype` / `level` | string | 否 | 试卷类型/范围 |

**响应 201**（`data`，PaperDetailSerializer，含已关联题目）：

```json
{
  "id": 3,
  "title": "三年级音乐自动组卷",
  "ptype": "formal",
  "subject": "music",
  "level": "class",
  "grade": "三年级",
  "duration": 30,
  "total_score": 20,
  "status": "draft",
  "creator": 2,
  "question_count": 4,
  "paper_questions": [
    { "id": 9, "paper": 3, "question": 1, "sort": 1, "score": 5, "question": { "id": 1, "stem": "以下哪个是高音谱号？", "qtype": "single", "options": [{ "key": "A", "text": "𝄞" }], "answer": "A", "score": 5 } }
  ]
}
```

#### E3 · #28 暂存（草稿）组卷

- **接口名**：按题目 id 列表暂存试卷
- `POST {{baseUrl}}/api/exam/papers/{id}/draft/`
- **角色**：教师/学校/区县/市州/省级

请求体：

```json
{ "question_ids": [1, 2, 3, 4] }
```

**响应 200**（`data`）：同 E2 的 PaperDetail（已按顺序关联题目并回填 `question_count`）。

#### E4 · #29 下载试卷材料（zip）

- **接口名**：下载试卷材料包
- `GET {{baseUrl}}/api/exam/papers/{id}/materials/`
- **角色**：教师/学校/区县/市州/省级

**响应 200**：文件流（`application/zip`），内容为试卷内所有题目的图片/音频等资源压缩包。

#### E5 · #30 下载试卷答案（txt）

- **接口名**：下载试卷答案
- `GET {{baseUrl}}/api/exam/papers/{id}/answers/`
- **角色**：教师/学校/区县/市州/省级

**响应 200**：文本流（`text/plain`），逐题列出答案。

---

### 链路 F：试卷 - 试题关联（PaperQuestion）

#### F1 · #31-#35 试题关联 CRUD

- **接口名**：试卷试题关联 列表 / 新增 / 详情 / 修改 / 删除

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/exam/paper-questions/` | 教师/学校/区县/市州/省级 |
| POST | `/api/exam/paper-questions/` | 教师/学校/区县/市州/省级 |
| GET | `/api/exam/paper-questions/{id}/` | 教师/学校/区县/市州/省级 |
| PUT | `/api/exam/paper-questions/{id}/` | 教师/学校/区县/市州/省级 |
| DELETE | `/api/exam/paper-questions/{id}/` | 教师/学校/区县/市州/省级 |

请求体（POST）：

```json
{ "paper": 3, "question": 1, "sort": 1, "score": 5 }
```

**响应**（`data`，单条 PaperQuestion）：

```json
{ "id": 10, "paper": 3, "question": 1, "sort": 1, "score": 5 }
```

> 一般用 E2/E3 自动关联，无需手工调；此接口供调整顺序/分值时用。

---

### 链路 G：试卷 - 发布（PaperPublish）

#### G1 · #36-#40 发布 CRUD

- **接口名**：发布记录 列表 / 新增 / 详情 / 修改 / 删除

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/exam/publishes/` | 教师/学校/区县/市州/省级 |
| POST | `/api/exam/publishes/` | 教师/学校/区县/市州/省级 |
| GET | `/api/exam/publishes/{id}/` | 教师/学校/区县/市州/省级 |
| PUT | `/api/exam/publishes/{id}/` | 教师/学校/区县/市州/省级 |
| DELETE | `/api/exam/publishes/{id}/` | 教师/学校/区县/市州/省级 |

请求体（POST，按班级发布）：

```json
{
  "paper": 3,
  "scope_type": "class",
  "target_class": 1,
  "target_school": 1,
  "grade": "三年级",
  "start_at": "2026-10-22T08:00:00+08:00",
  "end_at": "2026-10-22T18:00:00+08:00"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `paper` | number | 是 | 试卷 id |
| `scope_type` | string | 是 | class/school/region（决定 target 字段） |
| `target_class` | number | 否 | scope=class 时必填 |
| `target_school` | number | 否 | scope=school 时必填 |
| `target_region` | number | 否 | scope=region 时必填 |
| `grade` | string | 否 | 按年级限定 |
| `start_at` / `end_at` | string | 否 | 有效期（ISO8601 时间） |

> 校验：scope_type 与 target 字段必须匹配（class→target_class、school→target_school、region→target_region），否则返回业务错误。

**响应**（`data`，单条 PaperPublish）：

```json
{
  "id": 2,
  "paper": 3,
  "scope_type": "class",
  "grade": "三年级",
  "target_school": 1,
  "target_class": 1,
  "target_region": null,
  "start_at": "2026-10-22T08:00:00+08:00",
  "end_at": "2026-10-22T18:00:00+08:00",
  "status": "published"
}
```

#### G2 · #41 撤回发布

- **接口名**：撤回试卷发布
- `POST {{baseUrl}}/api/exam/publishes/{id}/recall/`
- **角色**：教师/学校/区县/市州/省级

**请求体**：无

**响应 200**：`{ "code": 0, "message": "撤回成功", "data": null }`（发布记录 status → 已撤回）。

---

### 链路 H（附）：答题记录 AI 评分入口（C 域保留）

> 这两个接口属于 C 模块「判分」域，但注册在 B 的 `exam/views.py` 中，此处列出便于联调，正式测试以 C 模块文档为准。

#### H1 · AI 单卷评分

- **接口名**：AI 评分单个答题记录
- `POST {{baseUrl}}/api/exam/answers/{id}/ai-grade/`
- **角色**：教师/学校/区县/市州/省级

请求体：

```json
{ "save": true }
```

**响应 200**（`data`）：该题 AI 判分结果（主观题型 short/listening/sight）。

#### H2 · AI 批量评分

- **接口名**：AI 批量评分答题卷
- `POST {{baseUrl}}/api/exam/answers/ai-grade-batch/`
- **角色**：教师/学校/区县/市州/省级

请求体：

```json
{ "sheet_id": 1, "save": true }
```

**响应 200**（`data`）：该卷所有主观题的 AI 判分结果。

---

## 五、负向 / 权限验证（建议做）

| 验证项 | 做法 | 预期 |
| --- | --- | --- |
| 教师不能建课程 | `teacher` 调 `POST /api/questionbank/courses/` | 403 |
| 学生不能写试题 | `student` 调 `POST /api/questionbank/questions/` | 403 |
| 教师不能审核 | `teacher` 调 `POST .../review/` | 403（仅题库管理员） |
| 组卷配置为空 | `qtype_config: []` | 400（非空校验） |
| 发布范围与目标不符 | `scope_type: "class"` 但只传 `target_school` | 400（交叉校验） |
| 未审核题被组卷引用 | 用 status=draft 的题 id 组卷 | 业务错误（仅 approved 可引用） |

---

## 六、关键参数速查

### 6.1 seed 造出的 id 参考

| 资源 | 值 | 说明 |
| --- | --- | --- |
| 音乐课程 | id=1 | code=music |
| 美术课程 | id=2 | code=art |
| 4 道已审核题 | id=1~4 | 单选×2、多选×1、判断×1，全部 approved |
| 三年级音乐正式测评 | id=1 | formal，总分 20，published |
| 发布记录 | id=1 | scope=class，命中三年级一班 |

> 以接口实际返回为准（`GET /api/questionbank/questions/`）。

### 6.2 枚举值速查

| 字段 | 取值 |
| --- | --- |
| `qtype` | single / multiple / judge / fill / short / listening / sight |
| `difficulty` | easy / medium / hard |
| `question.status` | draft / pending / approved / rejected |
| `ptype` | practice / formal |
| `level`（试卷） | class / school / region |
| `scope_type`（发布） | class / school / region |
| `rtype`（资源） | audio / image / video |
| `review.result` | approved / rejected |

---

## 七、常见问题排查

| 现象 | 原因与解决 |
| --- | --- |
| 登录后 401 | token 取 `data.access`，Header `Authorization: Bearer {{access}}` |
| 建课程 403 | 课程写操作仅题库管理员，换 `admin` 登录 |
| 组卷后没题目 | 引用的题必须是 `approved`；或 `qtype_config` 数量超出已审核题池 |
| 下载 materials/answers 是乱码 | 是文件流（zip/txt），用「下载」而非「发送」测试 |
| 发布后学生看不到 | 检查 scope_type/target 是否匹配学生所在班级，且未过期、未撤回 |
| 列表结构对不上 | 统一 `data.list` + `data.total` |

---

## 附：完整接口路径速查

| # | 方法 | 路径 | 角色 |
| --- | --- | --- | --- |
| 1 | POST | `/api/auth/login/` | 公开 |
| 2 | POST | `/api/auth/refresh/` | 公开 |
| 3 | GET | `/api/questionbank/courses/` | 学生/教师/题库管理员 |
| 4 | POST | `/api/questionbank/courses/` | 仅题库管理员 |
| 5 | GET | `/api/questionbank/courses/{id}/` | 学生/教师/题库管理员 |
| 6 | PUT | `/api/questionbank/courses/{id}/` | 仅题库管理员 |
| 7 | DELETE | `/api/questionbank/courses/{id}/` | 仅题库管理员 |
| 8 | GET | `/api/questionbank/chapters/` | 学生/教师/题库管理员 |
| 9 | POST | `/api/questionbank/chapters/` | 仅题库管理员 |
| 10 | GET | `/api/questionbank/chapters/{id}/` | 学生/教师/题库管理员 |
| 11 | PUT | `/api/questionbank/chapters/{id}/` | 仅题库管理员 |
| 12 | DELETE | `/api/questionbank/chapters/{id}/` | 仅题库管理员 |
| 13 | GET | `/api/questionbank/questions/` | 教师/题库管理员 |
| 14 | POST | `/api/questionbank/questions/` | 教师/题库管理员 |
| 15 | GET | `/api/questionbank/questions/{id}/` | 教师/题库管理员 |
| 16 | PUT | `/api/questionbank/questions/{id}/` | 教师/题库管理员 |
| 17 | DELETE | `/api/questionbank/questions/{id}/` | 教师/题库管理员 |
| 18 | POST | `/api/questionbank/questions/{id}/resources/` | 教师/题库管理员 |
| 19 | DELETE | `/api/questionbank/questions/{id}/resources/{rid}/` | 教师/题库管理员 |
| 20 | POST | `/api/questionbank/questions/{id}/review/` | 仅题库管理员 |
| 21 | GET | `/api/questionbank/questions/{id}/reviews/` | 仅题库管理员 |
| 22 | GET | `/api/exam/papers/` | 教师/学校/区县/市州/省级 |
| 23 | POST | `/api/exam/papers/` | 教师/学校/区县/市州/省级 |
| 24 | GET | `/api/exam/papers/{id}/` | 教师/学校/区县/市州/省级 |
| 25 | PUT | `/api/exam/papers/{id}/` | 教师/学校/区县/市州/省级 |
| 26 | DELETE | `/api/exam/papers/{id}/` | 教师/学校/区县/市州/省级 |
| 27 | POST | `/api/exam/papers/auto-generate/` | 教师/学校/区县/市州/省级 |
| 28 | POST | `/api/exam/papers/{id}/draft/` | 教师/学校/区县/市州/省级 |
| 29 | GET | `/api/exam/papers/{id}/materials/` | 教师/学校/区县/市州/省级 |
| 30 | GET | `/api/exam/papers/{id}/answers/` | 教师/学校/区县/市州/省级 |
| 31 | GET | `/api/exam/paper-questions/` | 教师/学校/区县/市州/省级 |
| 32 | POST | `/api/exam/paper-questions/` | 教师/学校/区县/市州/省级 |
| 33 | GET | `/api/exam/paper-questions/{id}/` | 教师/学校/区县/市州/省级 |
| 34 | PUT | `/api/exam/paper-questions/{id}/` | 教师/学校/区县/市州/省级 |
| 35 | DELETE | `/api/exam/paper-questions/{id}/` | 教师/学校/区县/市州/省级 |
| 36 | GET | `/api/exam/publishes/` | 教师/学校/区县/市州/省级 |
| 37 | POST | `/api/exam/publishes/` | 教师/学校/区县/市州/省级 |
| 38 | GET | `/api/exam/publishes/{id}/` | 教师/学校/区县/市州/省级 |
| 39 | PUT | `/api/exam/publishes/{id}/` | 教师/学校/区县/市州/省级 |
| 40 | DELETE | `/api/exam/publishes/{id}/` | 教师/学校/区县/市州/省级 |
| 41 | POST | `/api/exam/publishes/{id}/recall/` | 教师/学校/区县/市州/省级 |
| + | POST | `/api/exam/answers/{id}/ai-grade/` | 教师/学校/区县/市州/省级（C 域） |
| + | POST | `/api/exam/answers/ai-grade-batch/` | 教师/学校/区县/市州/省级（C 域） |
