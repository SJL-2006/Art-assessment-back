# C 模块（作答 · 判分 · 评分 · 统计 · 证书）Apifox 接口测试文档

> 适用对象：验收成员 C 交付的 26 个接口（测评作答、判分评分、学生端结果、数据统计、证书）。
> 本文档所有接口统一按同一模板编写：每个接口含 **接口编号、接口名称、请求方法、请求路径、请求头、权限角色、请求体 JSON、请求字段表、响应示例 JSON、响应字段表**。

---

## 1. 文档说明

### 1.1 接口清单

C 模块共 **26 个接口**，按业务分 5 组：

| 分组 | 接口编号 | 数量 | 说明 |
| --- | --- | --- | --- |
| 认证 | #1 - #2 | 2 | 登录、刷新令牌 |
| 测评作答 | #3 - #9 | 7 | 可作答列表 / 试卷详情 / 开始作答 / 保存 / 提交 / 记录 / 报告 |
| 学生端结果 | #10 - #13 | 4 | 我的成绩 / 成绩曲线 / 成长曲线 / 上传课外学习 |
| 判分与评分 | #14 - #20 | 7 | 查看学生数据 / 平时评分 / 模板 / 导入 / 补录 / 导出 |
| 数据统计 | #21 - #23 | 3 | 测评统计 / 统计导出 / 参与率导出 |
| 证书 | #24 - #28 | 5 | 我的证书 / 详情 / 下载 / 学生证书 / 导出 |

> 数据依赖：需先有 A 模块的组织/账号，B 模块的题库/试卷/发布，学生才能作答、判分、统计、发证。
> 注：B 模块文档中的 `#42 AI 单卷评分`、`#43 AI 批量评分` 也属于「判分」域（注册在 `answers` 路由），此处不重复列出。

---

## 2. 统一规范（三模块通用）

### 2.1 响应信封

所有接口（成功与失败）都包在统一信封中：

```json
{
  "code": 0,
  "message": "ok",
  "data": { }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| code | integer | 业务状态码，`0` 表示成功，非 0 表示失败 |
| message | string | 状态说明，成功为 `"ok"` |
| data | object/array/null | 业务数据，失败时为 `null` |

> 下文每个接口的「响应字段表」只描述 `data` 内部字段，`code`/`message` 不再重复。

### 2.2 分页结构

所有列表接口使用全局 `StandardPagination`（默认每页 20 条），`data` 结构固定为：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [ ],
    "total": 20,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| list | array | 当前页数据 |
| total | integer | 总条数 |
| page | integer | 当前页码 |
| page_size | integer | 每页条数 |

> 例外：`#11 我的成绩`、`#12 成绩曲线`、`#13 成长曲线`、`#16 查看学生成绩`、`#17 查看学生课外学习`、`#27 学生证书` 返回的数据**不分页**，直接放在 `data` 里。

### 2.3 错误响应

```json
{
  "code": 400,
  "message": "错误描述",
  "data": null
}
```

常见错误码：`401` 未认证 / `403` 无权限 / `404` 不存在 / `409` 冲突（重复提交、测评未开始/已结束）/ `400` 参数错误。

### 2.4 鉴权方式

除公开接口（#1 #2）外，其余接口均需在请求头携带 JWT：

```
Authorization: Bearer <access_token>
```

### 2.5 字段类型约定

| 类型 | 说明 | 示例 |
| --- | --- | --- |
| string | 字符串 | `"音乐"` |
| integer | 整数 | `1` |
| number | 数值（含小数） | `88.5` |
| boolean | 布尔 | `true` |
| array | 数组 | `[1, 2]` |
| object | 对象 | `{"key": "A"}` |
| string(decimal) | 十进制字符串（DRF 默认） | `"20.00"` |
| string(date-time) | 时间字符串（ISO8601） | `"2026-10-22T20:00:00+08:00"` |
| file | 二进制文件（multipart 上传） | — |
| null | 空值 | `null` |

> 类型提示：`answer_views.py` 里得分/总分多用 `str()` 输出（如 `"15.00"`）；`student_views.py`/`score_views.py`/`stats_views.py`/`certificate_views.py` 里多用 `float()`/`round()` 输出为 **number**（如 `15.0`、`0.75`）。请以各接口响应字段表为准。

---

## 3. 前置准备

### 3.1 迁移与演示数据

```bash
python manage.py makemigrations --merge --noinput
python manage.py migrate
python manage.py seed_demo
```

`seed_demo` 已为 C 模块备好完整数据链：

| 环节 | 内容 |
| --- | --- |
| 组织 | 四川省 → 成都市 → 锦江区 → 测试小学（SCH001） |
| 班级 | 三年级一班（CLS001） |
| 学生 | student（学号 S2024001），已加入班级并通过审核 |
| 教师 | teacher（李老师，归属测试小学） |
| 试卷 | 三年级音乐正式测评（formal，总分 20，4 道客观题） |
| 发布 | scope=class 命中三年级一班，状态 published |

### 3.2 启动服务

```bash
python manage.py runserver 8000
```

### 3.3 测试账号

| 账号 | 密码 | 角色 | 适合测试 |
| --- | --- | --- | --- |
| student | student123456 | 学生 | 作答 / 我的成绩 / 成长曲线 / 上传 / 我的证书 |
| teacher | teacher123456 | 教师 | 查看学生成绩、平时评分、导入/补录、证书查看 |
| school | school123456 | 学校管理员 | 判分评分、统计、证书查看 |
| district | district123456 | 区县管理员 | 补录、统计 |
| city | city123456 | 市州管理员 | 补录、统计 |
| province | province123456 | 省级管理员 | 统计 + 参与率导出 |
| admin | admin123456 | 超管 | 兜底访问全部接口 |

### 3.4 演示数据 id 参考

| 资源 | id | 说明 |
| --- | --- | --- |
| 学生 student | 4 | student_no=S2024001 |
| 音乐课程 | 1 | code=music |
| 三年级音乐正式测评 | 1 | formal，总分 20 |
| 发布记录 | 1 | scope=class，命中三年级一班 |

> 以接口实际返回为准（`GET /api/exam/my-assessments/`）。

---

## 4. Apifox 配置

### 4.1 导入接口

1. Apifox →「导入数据」→「OpenAPI / Swagger」→ 选择 `docs/schema.yml`。
2. 分组：exam（作答/成绩/统计/证书）。

### 4.2 环境变量

| 变量名 | 值 |
| --- | --- |
| baseUrl | http://127.0.0.1:8000 |
| access | （登录后自动写入） |
| student_id | 4（学生 id，供教师/学校接口用） |

### 4.3 全局 Header

```
Authorization: Bearer {{access}}
```

### 4.4 登录并提取 token

1. 调用 `#1 登录` 接口。
2. 后置操作「提取变量」：表达式 `$.data.access` → 写入变量 `access`。

> 建议：`student` 登录存一个环境（测作答/学生端），`teacher` 或 `school` 登录存一个环境（测判分/评分/统计/证书）。

---

## 5. 接口定义

### 5.1 认证

#### 5.1.1 #1 登录获取 JWT

| 属性 | 值 |
| --- | --- |
| 接口名称 | 登录获取 JWT |
| 请求方法 | POST |
| 请求路径 | /api/auth/login/ |
| 请求头 | 无 |
| 权限角色 | 公开 |

**请求体**（application/json）

```json
{
  "username": "student",
  "password": "student123456"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | string | 是 | 登录账号 |
| password | string | 是 | 登录密码 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "refresh": "<refresh_token>",
    "access": "<access_token>"
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| access | string | JWT 访问令牌 |
| refresh | string | JWT 刷新令牌 |

#### 5.1.2 #2 刷新访问令牌

| 属性 | 值 |
| --- | --- |
| 接口名称 | 刷新访问令牌 |
| 请求方法 | POST |
| 请求路径 | /api/auth/refresh/ |
| 请求头 | 无 |
| 权限角色 | 公开 |

**请求体**（application/json）

```json
{
  "refresh": "<refresh_token>"
}
```

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "access": "<new_access_token>",
    "refresh": "<new_refresh_token>"
  }
}
```

---

### 5.2 测评作答

#### 5.2.1 #3 我可作答的测评列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 我可作答的测评列表 |
| 请求方法 | GET |
| 请求路径 | /api/exam/my-assessments/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页条数，默认 20 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 1,
        "paper_id": 1,
        "title": "三年级音乐正式测评",
        "subject": "music",
        "subject_display": "音乐",
        "ptype": "formal",
        "ptype_display": "正式测评",
        "grade": "三年级",
        "duration": 30,
        "total_score": "20.00",
        "question_count": 4,
        "start_at": null,
        "end_at": null,
        "sheet_id": null,
        "is_submitted": false,
        "my_score": null
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 发布记录 id |
| paper_id | integer | 试卷 id |
| title | string | 试卷标题 |
| subject | string | 科目代码：music/art |
| subject_display | string | 科目中文名 |
| ptype | string | 类型：practice/formal |
| ptype_display | string | 类型中文名 |
| grade | string | 年级 |
| duration | integer | 限时（分钟） |
| total_score | string(decimal) | 试卷总分 |
| question_count | integer | 题目数量 |
| start_at | string(date-time)/null | 开始时间 |
| end_at | string(date-time)/null | 结束时间 |
| sheet_id | integer/null | 答卷 id（已开始时非空） |
| is_submitted | boolean | 是否已提交 |
| my_score | string(decimal)/null | 我的得分（提交后才有） |

#### 5.2.2 #4 试卷详情（含题目与资源）

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试卷详情（含题目与资源） |
| 请求方法 | GET |
| 请求路径 | /api/exam/my-assessments/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

> `{id}` 为发布记录 id（来自 #3 的 `id` 字段）。**已提交才返回答案与解析**。

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
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
      "total_score": "20.00",
      "question_count": 4
    },
    "start_at": null,
    "end_at": null,
    "is_open": true,
    "questions": [
      {
        "id": 1,
        "sort": 1,
        "qtype": "single",
        "qtype_display": "单选题",
        "difficulty": "easy",
        "grade": "三年级",
        "stem": "以下哪个是高音谱号？",
        "options": [
          { "key": "A", "text": "𝄞" },
          { "key": "B", "text": "𝄢" },
          { "key": "C", "text": "𝄡" },
          { "key": "D", "text": "𝄣" }
        ],
        "score": "5.00",
        "resources": []
      }
    ],
    "sheet": null,
    "my_answers": []
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 发布记录 id |
| paper | object | 试卷摘要（id/title/subject/subject_display/ptype/ptype_display/grade/duration/total_score/question_count） |
| start_at / end_at | string(date-time)/null | 时间窗口 |
| is_open | boolean | 当前是否可作答 |
| questions | array(object) | 题目列表 |
| questions[].id | integer | 题目 id |
| questions[].sort | integer | 题号 |
| questions[].qtype | string | 题型代码 |
| questions[].qtype_display | string | 题型中文名 |
| questions[].difficulty | string | 难度：easy/medium/hard |
| questions[].grade | string | 适用年级 |
| questions[].stem | string | 题干 |
| questions[].options | array(object) | 选项数组 `[{key, text}]` |
| questions[].score | string(decimal) | 分值 |
| questions[].resources | array(object) | 资源 `[{id, rtype, url}]` |
| questions[].answer | string | 答案（仅已提交后返回） |
| questions[].analysis | string | 解析（仅已提交后返回） |
| sheet | object/null | 答卷摘要（同 sheet_payload） |
| my_answers | array(object) | 已保存答案 `[{question_id, answer, score, is_correct}]` |

#### 5.2.3 #5 开始作答

| 属性 | 值 |
| --- | --- |
| 接口名称 | 开始作答 |
| 请求方法 | POST |
| 请求路径 | /api/exam/answer-sheets/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**请求体**（application/json）

```json
{
  "publish_id": 1
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| publish_id | integer | 二选一 | 发布记录 id（推荐） |
| paper_id | integer | 二选一 | 试卷 id（在可用范围内时等效） |

> 重复调用返回同一份答卷（幂等）；已提交会返回 `409`。

**响应示例**（200）

```json
{
  "code": 0,
  "message": "开始作答",
  "data": {
    "id": 1,
    "paper_id": 1,
    "publish_id": 1,
    "started_at": "2026-10-22T20:00:00+08:00",
    "submitted_at": null,
    "is_submitted": false,
    "total_score": "0.00"
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 答卷 id（后续保存/提交用） |
| paper_id | integer | 试卷 id |
| publish_id | integer | 发布记录 id |
| started_at | string(date-time) | 开始时间 |
| submitted_at | string(date-time)/null | 提交时间 |
| is_submitted | boolean | 是否已提交 |
| total_score | string(decimal) | 当前得分 |

#### 5.2.4 #6 保存答题进度

| 属性 | 值 |
| --- | --- |
| 接口名称 | 保存答题进度 |
| 请求方法 | PUT |
| 请求路径 | /api/exam/answer-sheets/{id}/answers/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**请求体**（application/json）

```json
{
  "answers": [
    { "question_id": 1, "answer": "A" },
    { "question_id": 3, "answer": "ACD" },
    { "question_id": 4, "answer": "正确" }
  ]
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| answers | array(object) | 是 | 答案数组，元素 `{question_id, answer}` |
| answers[].question_id | integer | 是 | 题目 id |
| answers[].answer | string | 是 | 作答内容（多选如 `"ACD"`，判断填 `"正确"`/`"错误"`） |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "保存成功",
  "data": {
    "sheet_id": 1,
    "saved": 3,
    "is_submitted": false
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| sheet_id | integer | 答卷 id |
| saved | integer | 保存的答案条数 |
| is_submitted | boolean | 是否已提交 |

#### 5.2.5 #7 提交答卷（自动判分）

| 属性 | 值 |
| --- | --- |
| 接口名称 | 提交答卷（自动判分） |
| 请求方法 | POST |
| 请求路径 | /api/exam/answer-sheets/{id}/submit/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**请求体**：无

**响应示例**（200）

```json
{
  "code": 0,
  "message": "提交成功",
  "data": {
    "id": 1,
    "paper_id": 1,
    "publish_id": 1,
    "started_at": "2026-10-22T20:00:00+08:00",
    "submitted_at": "2026-10-22T20:30:00+08:00",
    "is_submitted": true,
    "total_score": "20.00",
    "paper_total_score": "20.00",
    "correct_count": 4,
    "wrong_count": 0,
    "subjective_pending": 0,
    "pass": true
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 答卷 id |
| paper_id | integer | 试卷 id |
| publish_id | integer | 发布记录 id |
| started_at / submitted_at | string(date-time) | 开始/提交时间 |
| is_submitted | boolean | 是否已提交 |
| total_score | string(decimal) | 客观题自动判分得分 |
| paper_total_score | string(decimal) | 试卷总分 |
| correct_count | integer | 答对题数 |
| wrong_count | integer | 答错题数 |
| subjective_pending | integer | 待人工评分的主观题数 |
| pass | boolean | 是否及格（≥60%） |

> 提交后正式测评达到及格线会自动发放证书（见 #24）。

#### 5.2.6 #8 我的测评记录

| 属性 | 值 |
| --- | --- |
| 接口名称 | 我的测评记录 |
| 请求方法 | GET |
| 请求路径 | /api/exam/my-assessments/records/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "sheet_id": 1,
        "publish_id": 1,
        "paper_id": 1,
        "title": "三年级音乐正式测评",
        "subject": "music",
        "subject_display": "音乐",
        "ptype": "formal",
        "ptype_display": "正式测评",
        "total_score": "20.00",
        "my_score": "20.00",
        "is_submitted": true,
        "started_at": "2026-10-22T20:00:00+08:00",
        "submitted_at": "2026-10-22T20:30:00+08:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| sheet_id | integer | 答卷 id |
| publish_id | integer | 发布记录 id |
| paper_id | integer | 试卷 id |
| title | string | 试卷标题 |
| subject / subject_display | string | 科目代码/中文 |
| ptype / ptype_display | string | 类型代码/中文 |
| total_score | string(decimal) | 试卷总分 |
| my_score | string(decimal) | 我的得分 |
| is_submitted | boolean | 是否已提交 |
| started_at / submitted_at | string(date-time) | 开始/提交时间 |

#### 5.2.7 #9 测评统计分析报告

| 属性 | 值 |
| --- | --- |
| 接口名称 | 测评统计分析报告 |
| 请求方法 | GET |
| 请求路径 | /api/exam/my-assessments/{id}/report/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

> 需已提交答卷，否则返回 `400`（尚未提交）或 `404`（尚未开始）。

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sheet_id": 1,
    "publish_id": 1,
    "paper_title": "三年级音乐正式测评",
    "subject": "music",
    "subject_display": "音乐",
    "ptype": "formal",
    "total_score": "20.00",
    "my_score": "20.00",
    "correct_rate": 1.0,
    "score_rate": 1.0,
    "correct_count": 4,
    "wrong_count": 0,
    "subjective_count": 0,
    "question_count": 4,
    "class_average": "17.50",
    "class_size": 2,
    "submitted_at": "2026-10-22T20:30:00+08:00",
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
        "full_score": "5.00",
        "score": "5.00",
        "is_correct": true
      }
    ]
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| sheet_id / publish_id | integer | 答卷/发布 id |
| paper_title | string | 试卷标题 |
| subject / subject_display | string | 科目代码/中文 |
| ptype | string | 类型 |
| total_score | string(decimal) | 试卷总分 |
| my_score | string(decimal) | 我的得分 |
| correct_rate | number | 正确率（正确题数/总题数） |
| score_rate | number | 得分率（得分/总分） |
| correct_count / wrong_count / subjective_count / question_count | integer | 正确/错误/待判/总题数 |
| class_average | string(decimal) | 班级平均分 |
| class_size | integer | 已提交答卷人数 |
| submitted_at | string(date-time) | 提交时间 |
| details | array(object) | 逐题明细 |
| details[].question_id / sort / qtype / qtype_display / stem | — | 题目信息 |
| details[].my_answer | string | 我的作答 |
| details[].correct_answer | string | 参考答案 |
| details[].analysis | string | 解析 |
| details[].full_score | string(decimal) | 本题满分 |
| details[].score | string(decimal) | 本题得分 |
| details[].is_correct | boolean/null | 是否正确（主观题为 null） |

---

### 5.3 学生端结果

#### 5.3.1 #10 我的成绩

| 属性 | 值 |
| --- | --- |
| 接口名称 | 我的成绩 |
| 请求方法 | GET |
| 请求路径 | /api/exam/my-scores/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
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
        "date": "2026-10-22 20:30:00"
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
        "date": "2026-10-22 21:00:00"
      }
    ],
    "by_subject": [
      {
        "subject": "music",
        "subject_display": "音乐",
        "count": 2,
        "average_rate": 0.94
      }
    ]
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| exams | array(object) | 测评成绩点 |
| performances | array(object) | 平时表现评分点 |
| by_subject | array(object) | 按学科汇总 |
| (点).source | string | 来源：exam / daily |
| (点).title | string | 标题 |
| (点).subject / subject_display | string | 科目代码/中文 |
| (点).ptype | string | 类型（daily 表示平时表现） |
| (点).score | number | 得分 |
| (点).total_score | number | 满分 |
| (点).rate | number | 得分率（0-1） |
| (点).date | string | 时间 `YYYY-MM-DD HH:MM:SS` |
| by_subject[].subject / subject_display / count / average_rate | — | 学科汇总 |

#### 5.3.2 #11 成绩曲线

| 属性 | 值 |
| --- | --- |
| 接口名称 | 成绩曲线 |
| 请求方法 | GET |
| 请求路径 | /api/exam/my-scores/curve/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| subject | string | 否 | 按科目过滤：music / art |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
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
        "date": "2026-10-22 20:30:00"
      }
    ],
    "total": 1
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| points | array(object) | 成绩点（结构同 #10 的点，按时间升序） |
| total | integer | 成绩点数量 |

#### 5.3.3 #12 个人成长曲线

| 属性 | 值 |
| --- | --- |
| 接口名称 | 个人成长曲线 |
| 请求方法 | GET |
| 请求路径 | /api/exam/my-growth/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "series": [
      {
        "subject": "music",
        "subject_display": "音乐",
        "count": 1,
        "average_rate": 1.0,
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
            "date": "2026-10-22 20:30:00"
          }
        ]
      }
    ],
    "total": 1
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| series | array(object) | 按科目分组的成长曲线 |
| series[].subject / subject_display | string | 科目代码/中文 |
| series[].count | integer | 成绩点数量 |
| series[].average_rate | number | 平均得分率 |
| series[].points | array(object) | 成绩点（结构同 #10 的点） |
| total | integer | 成绩点总数 |

#### 5.3.4 #13 上传课外自主学习图片

| 属性 | 值 |
| --- | --- |
| 接口名称 | 上传课外自主学习图片 |
| 请求方法 | POST |
| 请求路径 | /api/exam/extracurricular/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |
| Content-Type | multipart/form-data |

**请求体**（multipart/form-data）

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| image | file | 是 | 图片文件 |
| title | string | 否 | 标题，默认「课外学习成果」 |
| description | string | 否 | 描述 |

**响应示例**（201）

```json
{
  "code": 0,
  "message": "上传成功",
  "data": {
    "id": 1,
    "title": "课外学习成果",
    "image": "http://127.0.0.1:8000/media/extracurricular/2026/10/demo.jpg",
    "description": "",
    "created_at": "2026-10-22T21:00:00+08:00"
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 记录 id |
| title | string | 标题 |
| image | string | 图片 URL |
| description | string | 描述 |
| created_at | string(date-time) | 创建时间 |

---

### 5.4 判分与评分

#### 5.4.1 #14 查看学生课外学习材料

| 属性 | 值 |
| --- | --- |
| 接口名称 | 查看学生课外学习材料 |
| 请求方法 | GET |
| 请求路径 | /api/exam/students/{student_id}/extracurricular/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "student_id": 4,
    "list": [
      {
        "id": 1,
        "title": "课外学习成果",
        "description": "",
        "image": "http://127.0.0.1:8000/media/extracurricular/2026/10/demo.jpg",
        "created_at": "2026-10-22T21:00:00+08:00"
      }
    ],
    "total": 1
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| student_id | integer | 学生 id |
| list | array(object) | 材料列表 |
| list[].id / title / description / image / created_at | — | 材料信息 |
| total | integer | 材料数量 |

#### 5.4.2 #15 查看学生测评成绩

| 属性 | 值 |
| --- | --- |
| 接口名称 | 查看学生测评成绩 |
| 请求方法 | GET |
| 请求路径 | /api/exam/students/{student_id}/scores/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
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
        "submitted_at": "2026-10-22T20:30:00+08:00"
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
        "created_at": "2026-10-22T21:00:00+08:00"
      }
    ],
    "subject_average": {
      "音乐": 54.0
    }
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| student | object | 学生摘要（id/username/real_name/student_no） |
| exams | array(object) | 测评成绩 |
| exams[].sheet_id / paper_id / title / subject / subject_display / ptype | — | 测评信息 |
| exams[].score / total_score | number | 得分/满分 |
| exams[].submitted_at | string(date-time) | 提交时间 |
| performances | array(object) | 平时表现评分 |
| performances[].id / course / klass / score / comment / scorer / created_at | — | 评分信息 |
| subject_average | object | 各学科均分 `{学科名: 均分}` |

#### 5.4.3 #16 为学生平时表现评分

| 属性 | 值 |
| --- | --- |
| 接口名称 | 为学生平时表现评分 |
| 请求方法 | POST |
| 请求路径 | /api/exam/students/{student_id}/scores/daily/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**请求体**（application/json）

```json
{
  "score": 88,
  "course_id": 1,
  "klass_id": 1,
  "comment": "课堂表现积极"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| score | number | 是 | 评分（0-100） |
| course_id | integer | 否 | 学科（课程）id |
| klass_id | integer | 否 | 班级 id（缺省取学生已通过审核的班级） |
| comment | string | 否 | 评语 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "评分成功",
  "data": {
    "id": 1,
    "student_id": 4,
    "score": 88.0,
    "course": "音乐",
    "comment": "课堂表现积极"
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 评分记录 id |
| student_id | integer | 学生 id |
| score | number | 评分 |
| course | string | 学科名称（空串表示未指定） |
| comment | string | 评语 |

#### 5.4.4 #17 成绩导入模板下载

| 属性 | 值 |
| --- | --- |
| 接口名称 | 成绩导入模板下载 |
| 请求方法 | GET |
| 请求路径 | /api/exam/scores/template/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**响应**（200）：Excel 文件 `成绩导入模板.xlsx`（列：学籍号、姓名、班级编号、学科、分数、评语）。

#### 5.4.5 #18 导入学生线下成绩

| 属性 | 值 |
| --- | --- |
| 接口名称 | 导入学生线下成绩 |
| 请求方法 | POST |
| 请求路径 | /api/exam/scores/import/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |
| Content-Type | multipart/form-data |

**请求体**（multipart/form-data）

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | Excel 文件（按 #17 模板格式） |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "导入完成",
  "data": {
    "total": 2,
    "success": 1,
    "failed": 1,
    "errors": [
      { "row": 3, "error": "学生不存在或不在管理范围内" }
    ]
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| total | integer | 处理总行数 |
| success | integer | 成功条数 |
| failed | integer | 失败条数 |
| errors | array(object) | 失败明细 `[{row, error}]` |

#### 5.4.6 #19 测评成绩补录

| 属性 | 值 |
| --- | --- |
| 接口名称 | 测评成绩补录 |
| 请求方法 | POST |
| 请求路径 | /api/exam/scores/supplement/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校管理员 / 区县管理员 / 市州管理员 |

**请求体**（application/json，可单条或多条）

```json
{
  "items": [
    {
      "student_id": 4,
      "score": 90,
      "course_id": 1,
      "klass_id": 1,
      "comment": "补录说明"
    }
  ]
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| items | array(object) | 否 | 补录数组（不传则把顶层对象当单条） |
| items[].student_id | integer | 二选一 | 学生 id |
| items[].student_no | string | 二选一 | 学籍号 |
| items[].score | number | 是 | 分数（0-100） |
| items[].course_id | integer | 否 | 学科 id |
| items[].klass_id | integer | 否 | 班级 id |
| items[].comment | string | 否 | 备注（自动加「测评补录」前缀） |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "补录完成",
  "data": {
    "success": 1,
    "failed": 0,
    "results": [
      {
        "id": 2,
        "student_id": 4,
        "student_no": "S2024001",
        "score": 90.0
      }
    ],
    "errors": []
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| success / failed | integer | 成功/失败条数 |
| results | array(object) | 成功明细 `[{id, student_id, student_no, score}]` |
| errors | array(object) | 失败明细 `[{index, error}]` |

#### 5.4.7 #20 导出学生所有成绩

| 属性 | 值 |
| --- | --- |
| 接口名称 | 导出学生所有成绩 |
| 请求方法 | GET |
| 请求路径 | /api/exam/students/{student_id}/scores/export/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**响应**（200）：Excel 文件 `<姓名>_成绩.xlsx`（列：类型、名称、学科、得分、满分、时间、评语）。

---

### 5.5 数据统计

#### 5.5.1 #21 测评数据统计

| 属性 | 值 |
| --- | --- |
| 接口名称 | 测评数据统计 |
| 请求方法 | GET |
| 请求路径 | /api/exam/stats/assessment/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校管理员 / 区县管理员 / 市州管理员 / 省级管理员 |

**请求参数**（Query，全部可选）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| school_id | integer | 否 | 按学校过滤（需有权限） |
| region_id | integer | 否 | 按地区过滤（区县/市州/省级可用） |
| grade | string | 否 | 按年级过滤 |
| subject | string | 否 | 按科目过滤：music/art |
| ptype | string | 否 | 按类型过滤：practice/formal |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "summary": {
      "student_total": 1,
      "participant_count": 1,
      "submission_count": 1,
      "participation_rate": 1.0,
      "average_score_rate": 1.0,
      "pass_rate": 1.0
    },
    "by_subject": [
      {
        "key": "music",
        "label": "音乐",
        "participant_count": 1,
        "submission_count": 1,
        "average_score_rate": 1.0,
        "pass_rate": 1.0
      }
    ],
    "by_grade": [
      {
        "key": "三年级",
        "label": "三年级",
        "participant_count": 1,
        "submission_count": 1,
        "average_score_rate": 1.0,
        "pass_rate": 1.0
      }
    ],
    "by_school": [
      {
        "key": "测试小学",
        "label": "测试小学",
        "participant_count": 1,
        "submission_count": 1,
        "average_score_rate": 1.0,
        "pass_rate": 1.0
      }
    ]
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| summary.student_total | integer | 学生总数 |
| summary.participant_count | integer | 参与人数 |
| summary.submission_count | integer | 提交份数 |
| summary.participation_rate | number | 参与率（0-1） |
| summary.average_score_rate | number | 平均得分率（0-1） |
| summary.pass_rate | number | 及格率（0-1） |
| by_subject / by_grade / by_school | array(object) | 分组统计 |
| (组).key / label | string | 分组键/名称 |
| (组).participant_count / submission_count | integer | 参与人数/提交份数 |
| (组).average_score_rate / pass_rate | number | 平均得分率/及格率 |

#### 5.5.2 #22 统计导出 Excel

| 属性 | 值 |
| --- | --- |
| 接口名称 | 测评数据统计导出 |
| 请求方法 | GET |
| 请求路径 | /api/exam/stats/assessment/export/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校管理员 / 区县管理员 / 市州管理员 / 省级管理员 |

**请求参数**：同 #21。

**响应**（200）：Excel 文件 `测评数据统计.xlsx`。

#### 5.5.3 #23 测评参与率导出

| 属性 | 值 |
| --- | --- |
| 接口名称 | 测评参与率导出 |
| 请求方法 | GET |
| 请求路径 | /api/exam/stats/participation/export/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅省级管理员 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| region_id | integer | 否 | 按区县过滤 |

**响应**（200）：Excel 文件 `测评参与率.xlsx`（列：市州、区县、学校、学生数、参与人数、参与率）。

---

### 5.6 证书

#### 5.6.1 #24 我的证书列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 我的证书列表 |
| 请求方法 | GET |
| 请求路径 | /api/exam/certificates/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页条数，默认 20 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 1,
        "title": "音乐正式测评证书",
        "subject": "music",
        "subject_display": "音乐",
        "student_id": 4,
        "student_name": "小明",
        "sheet_id": 1,
        "score": 20.0,
        "file": "http://127.0.0.1:8000/media/certificate_1.html",
        "created_at": "2026-10-22T20:30:00+08:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 证书 id |
| title | string | 证书标题 |
| subject / subject_display | string | 科目代码/中文 |
| student_id | integer | 学生 id |
| student_name | string | 学生姓名 |
| sheet_id | integer | 关联答卷 id |
| score | number/null | 成绩 |
| file | string | 证书文件 URL |
| created_at | string(date-time) | 颁发时间 |

#### 5.6.2 #25 证书详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 证书详情 |
| 请求方法 | GET |
| 请求路径 | /api/exam/certificates/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**响应示例**（200）：`data` 为单个证书对象（结构同 #24）。

#### 5.6.3 #26 下载证书

| 属性 | 值 |
| --- | --- |
| 接口名称 | 下载证书 |
| 请求方法 | GET |
| 请求路径 | /api/exam/certificates/{id}/download/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**响应**（200）：HTML 证书文件 `certificate_{id}.html`（无附件时自动生成）。

#### 5.6.4 #27 查看学生证书

| 属性 | 值 |
| --- | --- |
| 接口名称 | 查看学生证书 |
| 请求方法 | GET |
| 请求路径 | /api/exam/students/{student_id}/certificates/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "student_id": 4,
    "list": [
      {
        "id": 1,
        "title": "音乐正式测评证书",
        "subject": "music",
        "subject_display": "音乐",
        "student_id": 4,
        "student_name": "小明",
        "sheet_id": 1,
        "score": 20.0,
        "file": "http://127.0.0.1:8000/media/certificate_1.html",
        "created_at": "2026-10-22T20:30:00+08:00"
      }
    ],
    "total": 1
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| student_id | integer | 学生 id |
| list | array(object) | 证书列表（结构同 #24） |
| total | integer | 证书数量 |

#### 5.6.5 #28 导出学生证书

| 属性 | 值 |
| --- | --- |
| 接口名称 | 导出学生证书 |
| 请求方法 | GET |
| 请求路径 | /api/exam/students/{student_id}/certificates/export/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**响应**（200）：Excel 文件 `<姓名>_证书.xlsx`（列：证书编号、证书名称、学科、关联测评、成绩、颁发时间）。

---

## 6. 附录

### 6.1 角色权限矩阵

| 接口 | 允许角色 |
| --- | --- |
| 作答 / 我的成绩 / 成长曲线 / 上传 / 我的证书 | 学生 |
| 查看学生课外学习 / 成绩 / 平时评分 / 模板 / 导入 / 导出 / 证书查看 | 教师 / 学校管理员 |
| 成绩补录 | 学校管理员 / 区县管理员 / 市州管理员 |
| 测评统计 / 统计导出 | 学校管理员 / 区县管理员 / 市州管理员 / 省级管理员 |
| 参与率导出 | 仅省级管理员 |

### 6.2 枚举值

| 字段 | 取值 |
| --- | --- |
| subject | music / art |
| ptype | practice / formal |
| qtype | single / multiple / judge / fill / short / listening / sight |
| difficulty | easy / medium / hard |
| 成绩点 source | exam / daily |

### 6.3 接口路径速查

| # | 方法 | 路径 | 角色 |
| --- | --- | --- | --- |
| 1 | POST | /api/auth/login/ | 公开 |
| 2 | POST | /api/auth/refresh/ | 公开 |
| 3 | GET | /api/exam/my-assessments/ | 学生 |
| 4 | GET | /api/exam/my-assessments/{id}/ | 学生 |
| 5 | POST | /api/exam/answer-sheets/ | 学生 |
| 6 | PUT | /api/exam/answer-sheets/{id}/answers/ | 学生 |
| 7 | POST | /api/exam/answer-sheets/{id}/submit/ | 学生 |
| 8 | GET | /api/exam/my-assessments/records/ | 学生 |
| 9 | GET | /api/exam/my-assessments/{id}/report/ | 学生 |
| 10 | GET | /api/exam/my-scores/ | 学生 |
| 11 | GET | /api/exam/my-scores/curve/ | 学生 |
| 12 | GET | /api/exam/my-growth/ | 学生 |
| 13 | POST | /api/exam/extracurricular/ | 学生 |
| 14 | GET | /api/exam/students/{student_id}/extracurricular/ | 教师/学校 |
| 15 | GET | /api/exam/students/{student_id}/scores/ | 教师/学校 |
| 16 | POST | /api/exam/students/{student_id}/scores/daily/ | 教师/学校 |
| 17 | GET | /api/exam/scores/template/ | 教师/学校 |
| 18 | POST | /api/exam/scores/import/ | 教师/学校 |
| 19 | POST | /api/exam/scores/supplement/ | 学校/区县/市州 |
| 20 | GET | /api/exam/students/{student_id}/scores/export/ | 教师/学校 |
| 21 | GET | /api/exam/stats/assessment/ | 学校/区县/市州/省级 |
| 22 | GET | /api/exam/stats/assessment/export/ | 学校/区县/市州/省级 |
| 23 | GET | /api/exam/stats/participation/export/ | 省级 |
| 24 | GET | /api/exam/certificates/ | 学生 |
| 25 | GET | /api/exam/certificates/{id}/ | 学生 |
| 26 | GET | /api/exam/certificates/{id}/download/ | 学生 |
| 27 | GET | /api/exam/students/{student_id}/certificates/ | 教师/学校 |
| 28 | GET | /api/exam/students/{student_id}/certificates/export/ | 教师/学校 |

### 6.4 测试链路建议

1. **作答链路**（student）：#1 登录 → #3 列表 → #4 详情 → #5 开始 → #6 保存 → #7 提交 → #9 报告。
2. **学生端结果**（student）：#10 我的成绩 → #11 曲线 → #12 成长曲线 → #13 上传课外学习。
3. **判分评分**（teacher）：#14 查看课外学习 → #15 查看成绩 → #16 平时评分 → #17 模板 → #18 导入 → #19 补录 → #20 导出。
4. **统计**（province）：#21 统计 → #22 统计导出 → #23 参与率导出。
5. **证书**（student）：#24 列表 → #25 详情 → #26 下载；（teacher）→ #27 查看 → #28 导出。

### 6.5 常见问题

| 现象 | 原因与解决 |
| --- | --- |
| 我的作答列表为空 | 发布范围未命中该学生班级，或不在时间窗口，或已撤回 |
| 开始作答 409 | 测评未开始/已结束，或已提交 |
| 保存答案报「试题不属于本试卷」 | `question_id` 不在该试卷题目范围内 |
| 报告报「尚未开始/未提交」 | 需先 #5 开始、#7 提交 |
| 提交后没证书 | 仅 formal 测评且得分率 ≥60% 才发证 |
| 统计为 0 | 需有学生已提交答卷；教师/学校只能看本校数据 |
| 参与率导出 403 | 仅省级管理员可用 |
| 导出接口乱码 | 是文件流（xlsx/html），用「下载」而非「发送」测试 |
