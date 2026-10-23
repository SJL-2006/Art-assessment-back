# B 模块（题库 · 试卷）Apifox 接口测试文档

> 适用对象：验收成员 B 交付的题库（课程/章节/试题/资源/审核）与试卷（组卷/暂存/发布/下载）接口。
> 本文档所有接口统一按同一模板编写：每个接口含 **接口编号、接口名称、请求方法、请求路径、请求头、权限角色、请求体 JSON、请求字段表、响应示例 JSON、响应字段表**。

---

## 1. 文档说明

### 1.1 接口清单

B 模块共 **43 个接口**，按资源分 8 组：

| 分组 | 接口编号 | 数量 | 说明 |
| --- | --- | --- | --- |
| 认证 | #1 - #2 | 2 | 登录、刷新令牌 |
| 题库 - 课程 | #3 - #7 | 5 | Course CRUD |
| 题库 - 章节 | #8 - #12 | 5 | Chapter CRUD |
| 题库 - 试题 | #13 - #21 | 9 | Question CRUD + 资源上传/删除 + 审核 |
| 试卷 | #22 - #30 | 9 | Paper CRUD + 自动组卷 + 暂存 + 下载 |
| 试卷 - 试题关联 | #31 - #35 | 5 | PaperQuestion CRUD |
| 试卷 - 发布 | #36 - #41 | 6 | PaperPublish CRUD + 撤回 |
| 答题 AI 评分 | #42 - #43 | 2 | 主观题 AI 评分（C 域保留入口） |

> 数据依赖：B 模块的题库（课程/试题）是 A 模块「组织/账号」之上的资源；试卷又依赖题库。流程为 admin 建课程→建题→审核，teacher 组卷→发布，学生才能作答（C 模块）。

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

### 2.3 错误响应

```json
{
  "code": 400,
  "message": "错误描述",
  "data": null
}
```

常见错误码：`401` 未认证 / `403` 无权限 / `404` 不存在 / `409` 冲突 / `400` 参数错误。

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

> 说明：`Question.score`、`Paper.total_score`、`PaperQuestion.score` 等 `DecimalField` 经 DRF 序列化后为字符串（如 `"5.00"`）。

---

## 3. 前置准备

### 3.1 迁移与演示数据

```bash
python manage.py makemigrations --merge --noinput
python manage.py migrate
python manage.py seed_demo
```

`seed_demo` 已为 B 模块备好：课程「音乐/美术」、4 道已审核客观题、一张已发布试卷「三年级音乐正式测评」（formal，总分 20，scope=class）。

### 3.2 启动服务

```bash
python manage.py runserver 8000
```

### 3.3 测试账号

| 账号 | 密码 | 角色 | 适合测试 |
| --- | --- | --- | --- |
| admin | admin123456 | 题库管理员(超管) | 题库全部写操作、审核、兜底 |
| teacher | teacher123456 | 教师 | 试题写、试卷全部操作 |
| student | student123456 | 学生 | 仅查看课程/章节 |
| school | school123456 | 学校管理员 | 试卷读 |

### 3.4 演示数据 id 参考

| 资源 | id | 说明 |
| --- | --- | --- |
| 音乐课程 | 1 | code=music |
| 美术课程 | 2 | code=art |
| 4 道已审核题 | 1~4 | 单选×2、多选×1、判断×1，全部 approved |
| 三年级音乐正式测评 | 1 | formal，总分 20，published |
| 发布记录 | 1 | scope=class，命中三年级一班 |

> 以接口实际返回为准（`GET /api/questionbank/questions/`）。

---

## 4. Apifox 配置

### 4.1 导入接口

1. Apifox →「导入数据」→「OpenAPI / Swagger」→ 选择 `docs/schema.yml`。
2. 分组：题库（课程/章节/试题）、试卷（试卷/试题关联/发布）。

### 4.2 环境变量

| 变量名 | 值 |
| --- | --- |
| baseUrl | http://127.0.0.1:8000 |
| access | （登录后自动写入） |

### 4.3 全局 Header

```
Authorization: Bearer {{access}}
```

### 4.4 登录并提取 token

1. 调用 `#1 登录` 接口。
2. 后置操作「提取变量」：表达式 `$.data.access` → 写入变量 `access`。

> 建议：`admin` 登录存一个环境（测题库写/审核），`teacher` 登录存一个环境（测组卷/发布）。

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
  "username": "admin",
  "password": "admin123456"
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

### 5.2 题库 - 课程（Course）

#### 5.2.1 #3 课程列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 课程列表 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/courses/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 / 教师 / 题库管理员 |

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
        "name": "音乐",
        "code": "music",
        "description": "",
        "created_at": "2026-10-22T20:00:00+08:00",
        "updated_at": "2026-10-22T20:00:00+08:00",
        "is_deleted": false,
        "deleted_at": null
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 课程 id |
| name | string | 课程名称（唯一） |
| code | string | 课程代码 |
| description | string | 描述 |
| created_at | string(date-time) | 创建时间 |
| updated_at | string(date-time) | 更新时间 |
| is_deleted | boolean | 是否软删除 |
| deleted_at | string(date-time)/null | 删除时间 |

#### 5.2.2 #4 新增课程

| 属性 | 值 |
| --- | --- |
| 接口名称 | 新增课程 |
| 请求方法 | POST |
| 请求路径 | /api/questionbank/courses/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**请求体**（application/json）

```json
{
  "name": "舞蹈",
  "code": "dance",
  "description": "舞蹈课程"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| name | string | 是 | 课程名称（唯一） |
| code | string | 否 | 课程代码 |
| description | string | 否 | 描述 |

**响应示例**（201）：`data` 为新建课程对象（结构同 #3）。

#### 5.2.3 #5 课程详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 课程详情 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/courses/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 / 教师 / 题库管理员 |

**响应示例**（200）：`data` 为单个课程对象（结构同 #3）。

#### 5.2.4 #6 修改课程

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改课程 |
| 请求方法 | PUT |
| 请求路径 | /api/questionbank/courses/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**请求体**（application/json，同 #4）

**响应示例**（200）：`data` 为更新后的课程对象。

#### 5.2.5 #7 删除课程

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除课程 |
| 请求方法 | DELETE |
| 请求路径 | /api/questionbank/courses/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

### 5.3 题库 - 章节（Chapter）

#### 5.3.1 #8 章节列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 章节列表 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/chapters/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 / 教师 / 题库管理员 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| course | integer | 否 | 按课程 id 过滤 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 1,
        "course": 1,
        "name": "乐理基础",
        "parent": null,
        "sort": 1,
        "created_at": "2026-10-22T20:00:00+08:00",
        "updated_at": "2026-10-22T20:00:00+08:00",
        "is_deleted": false,
        "deleted_at": null
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
| id | integer | 章节 id |
| course | integer | 所属课程 id |
| name | string | 章节名称 |
| parent | integer/null | 父章节 id（可两级） |
| sort | integer | 排序值 |

#### 5.3.2 #9 新增章节

| 属性 | 值 |
| --- | --- |
| 接口名称 | 新增章节 |
| 请求方法 | POST |
| 请求路径 | /api/questionbank/chapters/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**请求体**（application/json）

```json
{
  "course": 1,
  "name": "乐理基础",
  "parent": null,
  "sort": 1
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| course | integer | 是 | 所属课程 id |
| name | string | 是 | 章节名称 |
| parent | integer | 否 | 父章节 id |
| sort | integer | 否 | 排序值 |

**响应示例**（201）：`data` 为新建章节对象（结构同 #8）。

#### 5.3.3 #10 章节详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 章节详情 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/chapters/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 / 教师 / 题库管理员 |

**响应示例**（200）：`data` 为单个章节对象（结构同 #8）。

#### 5.3.4 #11 修改章节

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改章节 |
| 请求方法 | PUT |
| 请求路径 | /api/questionbank/chapters/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**请求体**（application/json，同 #9）

**响应示例**（200）：`data` 为更新后的章节对象。

#### 5.3.5 #12 删除章节

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除章节 |
| 请求方法 | DELETE |
| 请求路径 | /api/questionbank/chapters/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

### 5.4 题库 - 试题（Question）

#### 5.4.1 #13 试题列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试题列表 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/questions/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 题库管理员 |

**请求参数**（Query，全部可选）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| course | integer | 否 | 按课程 id 过滤 |
| chapter | integer | 否 | 按章节 id 过滤 |
| qtype | string | 否 | 按题型过滤 |
| difficulty | string | 否 | 按难度过滤 |
| grade | string | 否 | 按年级过滤 |
| status | string | 否 | 按状态过滤 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 5,
        "course": 1,
        "chapter": 1,
        "qtype": "single",
        "difficulty": "easy",
        "grade": "三年级",
        "stem": "五线谱有几条线？",
        "options": [
          { "key": "A", "text": "3条" },
          { "key": "B", "text": "5条" },
          { "key": "C", "text": "7条" }
        ],
        "answer": "B",
        "analysis": "五线谱由五条平行横线组成。",
        "score": "5.00",
        "status": "draft",
        "creator": 1,
        "reviewer": null,
        "resources": [],
        "course_name": "音乐",
        "chapter_name": "乐理基础",
        "created_at": "2026-10-22T20:00:00+08:00",
        "updated_at": "2026-10-22T20:00:00+08:00",
        "is_deleted": false,
        "deleted_at": null
      }
    ],
    "total": 4,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 试题 id |
| course | integer | 课程 id |
| chapter | integer/null | 章节 id |
| qtype | string | 题型：single/multiple/judge/fill/short/listening/sight |
| difficulty | string | 难度：easy/medium/hard |
| grade | string | 适用年级 |
| stem | string | 题干 |
| options | array(object) | 选项数组 `[{key, text}]` |
| answer | string | 参考答案 |
| analysis | string | 解析 |
| score | string(decimal) | 分值 |
| status | string | 状态：draft/pending/approved/rejected |
| creator | integer/null | 创建人 id |
| reviewer | integer/null | 审核人 id |
| resources | array(object) | 资源列表 |
| course_name | string | 课程名称 |
| chapter_name | string | 章节名称 |

#### 5.4.2 #14 新增试题

| 属性 | 值 |
| --- | --- |
| 接口名称 | 新增试题 |
| 请求方法 | POST |
| 请求路径 | /api/questionbank/questions/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 题库管理员 |

**请求体**（application/json，示例：单选题）

```json
{
  "course": 1,
  "chapter": 1,
  "qtype": "single",
  "difficulty": "easy",
  "grade": "三年级",
  "stem": "五线谱有几条线？",
  "options": [
    { "key": "A", "text": "3条" },
    { "key": "B", "text": "5条" },
    { "key": "C", "text": "7条" }
  ],
  "answer": "B",
  "analysis": "五线谱由五条平行横线组成。",
  "score": 5,
  "status": "draft"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| course | integer | 是 | 课程 id |
| chapter | integer | 否 | 章节 id |
| qtype | string | 是 | 题型 |
| difficulty | string | 否 | 难度，默认 medium |
| grade | string | 否 | 适用年级 |
| stem | string | 是 | 题干 |
| options | array(object) | 否 | 选项数组（判断题可为空） |
| answer | string | 是 | 答案（多选如 `"ACD"`，判断填 `"正确"`/`"错误"`） |
| analysis | string | 否 | 解析 |
| score | number | 否 | 分值 |
| status | string | 否 | 状态，默认 draft |

**响应示例**（201）：`data` 为新建试题对象（结构同 #13）。

#### 5.4.3 #15 试题详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试题详情 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 题库管理员 |

**响应示例**（200）：`data` 为单个试题对象（结构同 #13）。

#### 5.4.4 #16 修改试题

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改试题 |
| 请求方法 | PUT |
| 请求路径 | /api/questionbank/questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 题库管理员 |

**请求体**（application/json，同 #14）

**响应示例**（200）：`data` 为更新后的试题对象。

#### 5.4.5 #17 删除试题

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除试题 |
| 请求方法 | DELETE |
| 请求路径 | /api/questionbank/questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 题库管理员 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

#### 5.4.6 #18 上传试题资源

| 属性 | 值 |
| --- | --- |
| 接口名称 | 上传试题资源 |
| 请求方法 | POST |
| 请求路径 | /api/questionbank/questions/{id}/resources/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 题库管理员 |
| Content-Type | multipart/form-data |

**请求体**（multipart/form-data）

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| rtype | string | 是 | 资源类型：audio / image / video |
| file | file | 是 | 上传的文件 |

**响应示例**（201）

```json
{
  "code": 0,
  "message": "资源上传成功",
  "data": {
    "id": 1,
    "question": 5,
    "rtype": "audio",
    "file": "http://127.0.0.1:8000/media/question/2026/10/demo.mp3",
    "created_at": "2026-10-22T20:00:00+08:00",
    "updated_at": "2026-10-22T20:00:00+08:00",
    "is_deleted": false,
    "deleted_at": null
  }
}
```

#### 5.4.7 #19 删除试题资源

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除试题资源 |
| 请求方法 | DELETE |
| 请求路径 | /api/questionbank/questions/{id}/resources/{rid}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 题库管理员 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "资源删除成功",
  "data": null
}
```

#### 5.4.8 #20 审核试题

| 属性 | 值 |
| --- | --- |
| 接口名称 | 审核试题 |
| 请求方法 | POST |
| 请求路径 | /api/questionbank/questions/{id}/review/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**请求体**（application/json）

```json
{
  "result": "approved",
  "comment": "答案无误"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| result | string | 是 | approved / rejected |
| comment | string | 否 | 审核意见 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "审核完成",
  "data": {
    "id": 1,
    "question": 5,
    "reviewer": 1,
    "result": "approved",
    "comment": "答案无误",
    "created_at": "2026-10-22T20:00:00+08:00",
    "updated_at": "2026-10-22T20:00:00+08:00",
    "is_deleted": false,
    "deleted_at": null
  }
}
```

> 审核通过后，试题 `status` 自动变为 `approved`（可被组卷引用）。

#### 5.4.9 #21 查看审核记录

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试题审核记录 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/questions/{id}/reviews/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": 1,
      "question": 5,
      "reviewer": 1,
      "result": "approved",
      "comment": "答案无误",
      "created_at": "2026-10-22T20:00:00+08:00",
      "updated_at": "2026-10-22T20:00:00+08:00",
      "is_deleted": false,
      "deleted_at": null
    }
  ]
}
```

> 注意：本接口 `data` 直接是数组（未分页）。

---

### 5.5 试卷（Paper）

#### 5.5.1 #22 试卷列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试卷列表 |
| 请求方法 | GET |
| 请求路径 | /api/exam/papers/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求参数**（Query，全部可选）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| subject | string | 否 | 科目：music/art |
| ptype | string | 否 | 类型：practice/formal |
| level | string | 否 | 范围：class/school/district/city/province |
| grade | string | 否 | 年级 |
| status | string | 否 | 状态：draft/published/closed |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 1,
        "title": "三年级音乐正式测评",
        "ptype": "formal",
        "subject": "music",
        "level": "class",
        "grade": "三年级",
        "duration": 30,
        "total_score": "20.00",
        "status": "published",
        "creator": 1,
        "question_count": 4,
        "created_at": "2026-10-22T20:00:00+08:00",
        "updated_at": "2026-10-22T20:00:00+08:00",
        "is_deleted": false,
        "deleted_at": null
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
| id | integer | 试卷 id |
| title | string | 试卷标题 |
| ptype | string | 类型：practice/formal |
| subject | string | 科目：music/art |
| level | string | 适用范围：class/school/district/city/province |
| grade | string | 年级 |
| duration | integer | 限时（分钟） |
| total_score | string(decimal) | 总分 |
| status | string | 状态：draft/published/closed |
| creator | integer/null | 创建人 id |
| question_count | integer | 题目数量 |

#### 5.5.2 #23 新增试卷

| 属性 | 值 |
| --- | --- |
| 接口名称 | 新增试卷 |
| 请求方法 | POST |
| 请求路径 | /api/exam/papers/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json）

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

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| title | string | 是 | 试卷标题 |
| subject | string | 是 | 科目：music/art |
| ptype | string | 否 | 类型，默认 practice |
| level | string | 否 | 范围，默认 class |
| grade | string | 否 | 年级 |
| duration | integer | 否 | 限时（分钟），默认 0 |
| total_score | number | 否 | 总分，默认 0 |
| status | string | 否 | 状态，默认 draft |

**响应示例**（201）：`data` 为新建试卷对象（结构同 #22）。

#### 5.5.3 #24 试卷详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试卷详情 |
| 请求方法 | GET |
| 请求路径 | /api/exam/papers/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）：`data` 为单个试卷对象（结构同 #22，列表接口返回基础结构）。

#### 5.5.4 #25 修改试卷

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改试卷 |
| 请求方法 | PUT |
| 请求路径 | /api/exam/papers/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json，同 #23）

**响应示例**（200）：`data` 为更新后的试卷对象。

#### 5.5.5 #26 删除试卷

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除试卷 |
| 请求方法 | DELETE |
| 请求路径 | /api/exam/papers/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

#### 5.5.6 #27 自动组卷

| 属性 | 值 |
| --- | --- |
| 接口名称 | 按配置自动组卷 |
| 请求方法 | POST |
| 请求路径 | /api/exam/papers/auto-generate/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json）

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

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| title | string | 是 | 试卷标题 |
| subject | string | 是 | 科目：music/art |
| grade | string | 否 | 年级 |
| chapter_ids | array(integer) | 否 | 限定章节范围 |
| qtype_config | array(object) | 是 | 组卷规则，元素 `{qtype, count, difficulty}`，非空 |
| total_score | number | 否 | 总分（不传按各题分值累加） |
| ptype | string | 否 | 类型，默认 practice |
| level | string | 否 | 范围，默认 class |

**响应示例**（201）

```json
{
  "code": 0,
  "message": "自动组卷成功",
  "data": {
    "id": 3,
    "title": "三年级音乐自动组卷",
    "ptype": "formal",
    "subject": "music",
    "level": "class",
    "grade": "三年级",
    "duration": 0,
    "total_score": "20.00",
    "status": "draft",
    "creator": 2,
    "question_count": 4,
    "paper_questions": [
      {
        "id": 9,
        "paper": 3,
        "question": {
          "id": 1,
          "course": 1,
          "chapter": null,
          "qtype": "single",
          "difficulty": "easy",
          "grade": "三年级",
          "stem": "以下哪个是高音谱号？",
          "options": [
            { "key": "A", "text": "𝄞" },
            { "key": "B", "text": "𝄢" },
            { "key": "C", "text": "𝄡" },
            { "key": "D", "text": "𝄣" }
          ],
          "answer": "A",
          "analysis": "",
          "score": "5.00",
          "status": "approved",
          "creator": 1,
          "reviewer": 1,
          "resources": [],
          "course_name": "音乐",
          "chapter_name": null
        },
        "sort": 1,
        "score": "5.00"
      }
    ],
    "created_at": "2026-10-22T20:00:00+08:00",
    "updated_at": "2026-10-22T20:00:00+08:00",
    "is_deleted": false,
    "deleted_at": null
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 试卷 id |
| title / ptype / subject / level / grade / duration / status / creator | — | 同 #22 |
| total_score | string(decimal) | 总分 |
| question_count | integer | 题目数量 |
| paper_questions | array(object) | 已关联题目，每项含 `question`（完整题目）、`sort`（题号）、`score`（分值） |

#### 5.5.7 #28 暂存（草稿）组卷

| 属性 | 值 |
| --- | --- |
| 接口名称 | 按题目 id 列表暂存试卷 |
| 请求方法 | POST |
| 请求路径 | /api/exam/papers/{id}/draft/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json）

```json
{
  "question_ids": [1, 2, 3, 4]
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| question_ids | array(integer) | 是 | 试题 id 列表（按顺序重建关联） |

**响应示例**（200）：`data` 为 PaperDetail（结构同 #27，含 paper_questions）。

#### 5.5.8 #29 下载试卷材料（zip）

| 属性 | 值 |
| --- | --- |
| 接口名称 | 下载试卷材料包 |
| 请求方法 | GET |
| 请求路径 | /api/exam/papers/{id}/materials/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应**（200）：二进制文件流 `application/zip`，内容为试卷内题目的音频/图片资源压缩包。

#### 5.5.9 #30 下载试卷答案（txt）

| 属性 | 值 |
| --- | --- |
| 接口名称 | 下载试卷答案 |
| 请求方法 | GET |
| 请求路径 | /api/exam/papers/{id}/answers/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应**（200）：文本流 `text/plain; charset=utf-8`，逐题列出答案与解析。

---

### 5.6 试卷 - 试题关联（PaperQuestion）

#### 5.6.1 #31 试题关联列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试卷试题关联列表 |
| 请求方法 | GET |
| 请求路径 | /api/exam/paper-questions/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 1,
        "paper": 1,
        "question": 1,
        "sort": 1,
        "score": "5.00",
        "created_at": "2026-10-22T20:00:00+08:00",
        "updated_at": "2026-10-22T20:00:00+08:00",
        "is_deleted": false,
        "deleted_at": null
      }
    ],
    "total": 4,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 关联 id |
| paper | integer | 试卷 id |
| question | integer | 试题 id |
| sort | integer | 题号 |
| score | string(decimal) | 分值 |

#### 5.6.2 #32 新增试题关联

| 属性 | 值 |
| --- | --- |
| 接口名称 | 新增试卷试题关联 |
| 请求方法 | POST |
| 请求路径 | /api/exam/paper-questions/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json）

```json
{
  "paper": 3,
  "question": 1,
  "sort": 1,
  "score": 5
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| paper | integer | 是 | 试卷 id |
| question | integer | 是 | 试题 id |
| sort | integer | 否 | 题号 |
| score | number | 否 | 分值 |

**响应示例**（201）：`data` 为新建关联对象（结构同 #31）。

#### 5.6.3 #33 试题关联详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试卷试题关联详情 |
| 请求方法 | GET |
| 请求路径 | /api/exam/paper-questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）：`data` 为单个关联对象（结构同 #31）。

#### 5.6.4 #34 修改试题关联

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改试卷试题关联 |
| 请求方法 | PUT |
| 请求路径 | /api/exam/paper-questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json，同 #32）

**响应示例**（200）：`data` 为更新后的关联对象。

#### 5.6.5 #35 删除试题关联

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除试卷试题关联 |
| 请求方法 | DELETE |
| 请求路径 | /api/exam/paper-questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

> 一般用 #27/#28 自动关联，此接口供调整顺序/分值时用。

---

### 5.7 试卷 - 发布（PaperPublish）

#### 5.7.1 #36 发布记录列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 发布记录列表 |
| 请求方法 | GET |
| 请求路径 | /api/exam/publishes/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 1,
        "paper": 1,
        "scope_type": "class",
        "grade": "三年级",
        "target_school": 1,
        "target_class": 1,
        "target_region": null,
        "start_at": "2026-10-22T08:00:00+08:00",
        "end_at": "2026-10-22T18:00:00+08:00",
        "status": "published",
        "created_at": "2026-10-22T20:00:00+08:00",
        "updated_at": "2026-10-22T20:00:00+08:00",
        "is_deleted": false,
        "deleted_at": null
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
| paper | integer | 试卷 id |
| scope_type | string | 范围类型：class/school/grade/region |
| grade | string | 年级 |
| target_school | integer/null | 目标学校 id |
| target_class | integer/null | 目标班级 id |
| target_region | integer/null | 目标行政区 id |
| start_at | string(date-time)/null | 开始时间 |
| end_at | string(date-time)/null | 结束时间 |
| status | string | 状态：published/recalled |

#### 5.7.2 #37 发布试卷

| 属性 | 值 |
| --- | --- |
| 接口名称 | 发布试卷 |
| 请求方法 | POST |
| 请求路径 | /api/exam/publishes/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json，按班级发布）

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

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| paper | integer | 是 | 试卷 id（状态须为 draft/published） |
| scope_type | string | 是 | 范围类型：class/school/grade/region |
| target_class | integer | 否 | scope=class 时必填 |
| target_school | integer | 否 | scope=class/school 时必填 |
| target_region | integer | 否 | scope=region 时必填 |
| grade | string | 否 | 年级 |
| start_at | string(date-time) | 否 | 开始时间 |
| end_at | string(date-time) | 否 | 结束时间 |

> 交叉校验：scope_type 与 target 字段必须匹配（class→target_class、school→target_school、region→target_region）。

**响应示例**（201）

```json
{
  "code": 0,
  "message": "发布成功",
  "data": {
    "id": 2,
    "paper": 3,
    "scope_type": "class",
    "grade": "三年级",
    "target_school": 1,
    "target_class": 1,
    "target_region": null,
    "start_at": "2026-10-22T08:00:00+08:00",
    "end_at": "2026-10-22T18:00:00+08:00",
    "status": "published",
    "created_at": "2026-10-22T20:00:00+08:00",
    "updated_at": "2026-10-22T20:00:00+08:00",
    "is_deleted": false,
    "deleted_at": null
  }
}
```

#### 5.7.3 #38 发布记录详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 发布记录详情 |
| 请求方法 | GET |
| 请求路径 | /api/exam/publishes/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）：`data` 为单个发布记录（结构同 #36）。

#### 5.7.4 #39 修改发布记录

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改发布记录 |
| 请求方法 | PUT |
| 请求路径 | /api/exam/publishes/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json，同 #37）

**响应示例**（200）：`data` 为更新后的发布记录。

#### 5.7.5 #40 删除发布记录

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除发布记录 |
| 请求方法 | DELETE |
| 请求路径 | /api/exam/publishes/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

#### 5.7.6 #41 撤回发布

| 属性 | 值 |
| --- | --- |
| 接口名称 | 撤回试卷发布 |
| 请求方法 | POST |
| 请求路径 | /api/exam/publishes/{id}/recall/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**：无

**响应示例**（200）

```json
{
  "code": 0,
  "message": "撤回成功",
  "data": {
    "id": 2,
    "paper": 3,
    "scope_type": "class",
    "grade": "三年级",
    "target_school": 1,
    "target_class": 1,
    "target_region": null,
    "start_at": null,
    "end_at": null,
    "status": "recalled",
    "created_at": "2026-10-22T20:00:00+08:00",
    "updated_at": "2026-10-22T20:00:00+08:00",
    "is_deleted": false,
    "deleted_at": null
  }
}
```

---

### 5.8 答题 AI 评分（C 域保留入口）

> 这两个接口属于 C 模块「判分」域，但注册在 B 的 `exam/views.py` 中，此处列出便于联调。

#### 5.8.1 #42 AI 单卷评分

| 属性 | 值 |
| --- | --- |
| 接口名称 | AI 评分单个答题记录 |
| 请求方法 | POST |
| 请求路径 | /api/exam/answers/{id}/ai-grade/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**请求体**（application/json，可省略）

```json
{
  "save": true
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| save | boolean | 否 | 是否把评分写回数据库，默认 true |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "answer_id": 12,
    "score": 4.0,
    "max_score": 5.0,
    "feedback": "回答基本正确，但表述不够完整。",
    "suggestions": "可补充关于时值的说明。",
    "saved": true
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| answer_id | integer | 答题明细 id |
| score | number | AI 评分得分 |
| max_score | number | 该题满分 |
| feedback | string | 评分反馈 |
| suggestions | string | 改进建议 |
| saved | boolean | 是否已写回数据库 |

#### 5.8.2 #43 AI 批量评分

| 属性 | 值 |
| --- | --- |
| 接口名称 | AI 批量评分答题卷 |
| 请求方法 | POST |
| 请求路径 | /api/exam/answers/ai-grade-batch/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**请求体**（application/json）

```json
{
  "sheet_id": 1,
  "save": true
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| sheet_id | integer | 是 | 答卷 id |
| save | boolean | 否 | 是否写回数据库，默认 true |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sheet_id": 1,
    "save": true,
    "results": [
      {
        "answer_id": 12,
        "score": 4.0,
        "max_score": 5.0,
        "feedback": "回答基本正确。"
      }
    ],
    "total": 1
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| sheet_id | integer | 答卷 id |
| save | boolean | 是否写回 |
| results | array(object) | 逐题评分结果（含 skipped/error 情况） |
| total | integer | 处理条数 |

---

## 6. 附录

### 6.1 角色权限矩阵

| 接口 | 允许角色 |
| --- | --- |
| 课程/章节 读 | 学生 / 教师 / 题库管理员 |
| 课程/章节 写 | 仅题库管理员 |
| 试题 CRUD + 资源 | 教师 / 题库管理员 |
| 试题审核 + 审核记录 | 仅题库管理员 |
| 试卷 / 发布 / 试题关联 | 教师 / 学校 / 区县 / 市州 / 省级 |
| AI 评分 | 教师 / 学校 |

### 6.2 枚举值

| 字段 | 取值 |
| --- | --- |
| qtype | single / multiple / judge / fill / short / listening / sight |
| difficulty | easy / medium / hard |
| 试题 status | draft / pending / approved / rejected |
| ptype | practice / formal |
| 试卷 level | class / school / district / city / province |
| 发布 scope_type | class / school / grade / region |
| 发布 status | published / recalled |
| 资源 rtype | audio / image / video |
| 审核 result | approved / rejected |

### 6.3 接口路径速查

| # | 方法 | 路径 | 角色 |
| --- | --- | --- | --- |
| 1 | POST | /api/auth/login/ | 公开 |
| 2 | POST | /api/auth/refresh/ | 公开 |
| 3 | GET | /api/questionbank/courses/ | 学生/教师/题库管理员 |
| 4 | POST | /api/questionbank/courses/ | 仅题库管理员 |
| 5 | GET | /api/questionbank/courses/{id}/ | 学生/教师/题库管理员 |
| 6 | PUT | /api/questionbank/courses/{id}/ | 仅题库管理员 |
| 7 | DELETE | /api/questionbank/courses/{id}/ | 仅题库管理员 |
| 8 | GET | /api/questionbank/chapters/ | 学生/教师/题库管理员 |
| 9 | POST | /api/questionbank/chapters/ | 仅题库管理员 |
| 10 | GET | /api/questionbank/chapters/{id}/ | 学生/教师/题库管理员 |
| 11 | PUT | /api/questionbank/chapters/{id}/ | 仅题库管理员 |
| 12 | DELETE | /api/questionbank/chapters/{id}/ | 仅题库管理员 |
| 13 | GET | /api/questionbank/questions/ | 教师/题库管理员 |
| 14 | POST | /api/questionbank/questions/ | 教师/题库管理员 |
| 15 | GET | /api/questionbank/questions/{id}/ | 教师/题库管理员 |
| 16 | PUT | /api/questionbank/questions/{id}/ | 教师/题库管理员 |
| 17 | DELETE | /api/questionbank/questions/{id}/ | 教师/题库管理员 |
| 18 | POST | /api/questionbank/questions/{id}/resources/ | 教师/题库管理员 |
| 19 | DELETE | /api/questionbank/questions/{id}/resources/{rid}/ | 教师/题库管理员 |
| 20 | POST | /api/questionbank/questions/{id}/review/ | 仅题库管理员 |
| 21 | GET | /api/questionbank/questions/{id}/reviews/ | 仅题库管理员 |
| 22 | GET | /api/exam/papers/ | 教师/学校/区县/市州/省级 |
| 23 | POST | /api/exam/papers/ | 教师/学校/区县/市州/省级 |
| 24 | GET | /api/exam/papers/{id}/ | 教师/学校/区县/市州/省级 |
| 25 | PUT | /api/exam/papers/{id}/ | 教师/学校/区县/市州/省级 |
| 26 | DELETE | /api/exam/papers/{id}/ | 教师/学校/区县/市州/省级 |
| 27 | POST | /api/exam/papers/auto-generate/ | 教师/学校/区县/市州/省级 |
| 28 | POST | /api/exam/papers/{id}/draft/ | 教师/学校/区县/市州/省级 |
| 29 | GET | /api/exam/papers/{id}/materials/ | 教师/学校/区县/市州/省级 |
| 30 | GET | /api/exam/papers/{id}/answers/ | 教师/学校/区县/市州/省级 |
| 31 | GET | /api/exam/paper-questions/ | 教师/学校/区县/市州/省级 |
| 32 | POST | /api/exam/paper-questions/ | 教师/学校/区县/市州/省级 |
| 33 | GET | /api/exam/paper-questions/{id}/ | 教师/学校/区县/市州/省级 |
| 34 | PUT | /api/exam/paper-questions/{id}/ | 教师/学校/区县/市州/省级 |
| 35 | DELETE | /api/exam/paper-questions/{id}/ | 教师/学校/区县/市州/省级 |
| 36 | GET | /api/exam/publishes/ | 教师/学校/区县/市州/省级 |
| 37 | POST | /api/exam/publishes/ | 教师/学校/区县/市州/省级 |
| 38 | GET | /api/exam/publishes/{id}/ | 教师/学校/区县/市州/省级 |
| 39 | PUT | /api/exam/publishes/{id}/ | 教师/学校/区县/市州/省级 |
| 40 | DELETE | /api/exam/publishes/{id}/ | 教师/学校/区县/市州/省级 |
| 41 | POST | /api/exam/publishes/{id}/recall/ | 教师/学校/区县/市州/省级 |
| 42 | POST | /api/exam/answers/{id}/ai-grade/ | 教师/学校 |
| 43 | POST | /api/exam/answers/ai-grade-batch/ | 教师/学校 |

### 6.4 常见问题

| 现象 | 原因与解决 |
| --- | --- |
| 建课程 403 | 课程写操作仅题库管理员，换 `admin` 登录 |
| 组卷后没题目 | 引用的题必须是 `approved`；或 `qtype_config` 数量超出已审核题池 |
| 下载 materials/answers 是乱码 | 是文件流（zip/txt），用「下载」而非「发送」测试 |
| 发布后学生看不到 | 检查 scope_type/target 是否匹配学生所在班级，且未过期、未撤回 |
| 自动组卷报「仅找到 N 道题」 | 已审核题库中该题型/难度数量不足 |
| 列表结构对不上 | 统一 `data.list` + `data.total` |
