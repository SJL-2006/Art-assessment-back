# A 模块（基础底座 · 账号组织）Apifox 测试文档

> 适用对象：负责验收成员 A 交付的基础底座接口（认证、用户、行政区、学校、班级、账号管理、操作日志）。
> 每个接口都给出 **接口名、方法/路径、角色、请求 JSON、响应 JSON 字段**，按「准备 → 导入 → 认证 → 分链路逐步测试」顺序操作即可。

---

## 〇、接口总览

A 模块共 **37 个业务接口**（+ 1 个补充的科任教师申请），按资源分 6 组：

| 组 | 接口 | 数量 | 调用角色 |
| --- | --- | --- | --- |
| 认证 | #1-#2 | 2 | 公开 |
| 用户 | #3-#6 | 4 | 公开 / 登录用户 |
| 组织（行政区+学校） | #7-#16 | 10 | 市州/省级/区县（按接口分层） |
| 班级 | #17-#27 | 11 | 学生 / 教师 / 学校 |
| 账号管理 | #28-#36 | 9 | 学校 / 区县 / 市州 / 省级 |
| 操作日志 | #37 | 1 | 仅省级 / 题库管理员 |

> 说明：A 模块是「数据底座」，B 的题库/试卷、C 的作答/证书都依赖 A 造出的账号、行政区、学校、班级。建议先测 A，再测 B/C。

---

## 一、前置准备（跑起来）

### 1.1 修迁移冲突（若尚未处理）

```bash
python manage.py makemigrations --merge --noinput
python manage.py migrate
```

### 1.2 初始化演示数据

```bash
python manage.py seed_demo
```

幂等命令，造好：行政区三级（四川省→成都市→锦江区）、学校（测试小学）、班级（三年级一班）、学生入班，以及 7 个角色账号。

### 1.3 启动服务

```bash
python manage.py runserver 8000
```

### 1.4 账号速查表（密码即角色名 + 123456）

| 账号 | 密码 | 角色 | 适合测的接口 |
| --- | --- | --- | --- |
| `student` | `student123456` | 学生 | 班级 join/quit/change、查详情 |
| `teacher` | `teacher123456` | 教师 | 班级 CRUD、审核、materials |
| `school` | `school123456` | 学校管理员 | 班级、账号管理、region/school 查看 |
| `district` | `district123456` | 区县管理员 | school CRUD、账号管理 |
| `city` | `city123456` | 市州管理员 | region 写、school CRUD、账号 |
| `province` | `province123456` | 省级管理员 | region 全部、日志、账号 |
| `admin` | `admin123456` | 题库管理员(超管) | 日志、题库、兜底排查 |

---

## 二、把接口导入 Apifox

A/B/C 全量接口的统一 OpenAPI 已生成在 `docs/schema.yml`（含中文分组与接口名）：

1. Apifox →「导入数据」→「OpenAPI / Swagger」→ 选择 `docs/schema.yml`。
2. 自动生成分组：认证 / 用户 / 组织 / 班级 / 账号 / 日志 / 题库 / 试卷 / 答卷 / 证书。

> 若 `schema.yml` 与最新代码不同步，可重新生成：`python manage.py spectacular --file docs/schema.yml`。
> 也可直接用浏览器打开 `http://127.0.0.1:8000/api/docs/`（Swagger UI）对照。

---

## 三、环境与认证

### 3.1 统一响应信封

所有接口响应都包在统一信封里：

```json
{ "code": 0, "message": "ok", "data": { ... } }
```

错误时：`{ "code": <非0>, "message": "错误描述", "data": null }`（部分接口附带 `detail` 与 `code`）。

### 3.2 建环境 + 登录

1. 环境变量：`baseUrl` = `http://127.0.0.1:8000`、`access` = 空。
2. 全局 Header：`Authorization: Bearer {{access}}`。
3. 登录：`POST {{baseUrl}}/api/auth/login/`，body `{ "username": "province", "password": "province123456" }`。
4. 后置操作：提取 `$.data.access` → 写入 `access`。

**多角色切换**：换角色 = 换账号登录 = 重新提取 token。建议建 `本地-学生`、`本地-教师`、`本地-省管理` 等多个环境缓存 token。

---

## 四、分链路逐步测试（每步含完整 JSON）

> 公共字段说明：继承 BaseModel 的资源（行政区/学校/班级/课程/试题/试卷等）响应都会额外带 `id`、`created_at`、`updated_at`、`is_deleted`、`deleted_at` 这 5 个公共字段，下面 JSON 里不逐个重复，只在首次出现时列出。

---

### 链路 A：认证（公开接口，无需 token）

#### A1 · #1 登录获取 JWT

- **接口名**：登录并获取 JWT
- `POST {{baseUrl}}/api/auth/login/`
- **角色**：公开

请求体：

```json
{ "username": "province", "password": "province123456" }
```

响应 200（`data`）：

```json
{ "refresh": "eyJ...refresh", "access": "eyJ...access" }
```

#### A2 · #2 刷新访问令牌

- **接口名**：刷新访问令牌
- `POST {{baseUrl}}/api/auth/refresh/`
- **角色**：公开

请求体：

```json
{ "refresh": "eyJ...refresh" }
```

响应 200（`data`）：

```json
{ "access": "eyJ...new_access", "refresh": "eyJ...new_refresh" }
```

---

### 链路 B：用户（公开 + 登录用户）

#### B1 · #3 用户注册

- **接口名**：用户注册
- `POST {{baseUrl}}/api/users/register/`
- **角色**：公开

请求体：

```json
{
  "username": "stu999",
  "password": "pass12345Aa",
  "role": "student",
  "real_name": "测试学生",
  "phone": "13800000000",
  "student_no": "S2024999",
  "school": 1,
  "region": 3
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 登录名 |
| `password` | string | 是 | 需过 Django 密码强度校验（≥8位、不能纯数字） |
| `role` | string | 否 | student/teacher/school/district/city/province/qb_admin，默认 student |
| `real_name` / `phone` / `student_no` | string | 否 | 可空 |
| `school` / `region` | number | 否 | 所属学校/行政区 id |

响应 201（`data`，UserSerializer）：

```json
{
  "id": 10,
  "username": "stu999",
  "real_name": "测试学生",
  "phone": "13800000000",
  "avatar": "",
  "role": "student",
  "role_display": "学生",
  "student_no": "S2024999",
  "school": 1,
  "region": 3,
  "email": "",
  "date_joined": "2026-10-22T20:00:00+08:00"
}
```

#### B2 · #4 查询当前用户

- **接口名**：获取当前用户信息
- `GET {{baseUrl}}/api/users/me/`
- **角色**：登录用户

**请求参数**：无

**响应 200**（`data`）：同 B1 的 UserSerializer 结构。

#### B3 · #5 修改个人信息

- **接口名**：修改当前用户信息
- `PUT {{baseUrl}}/api/users/me/`
- **角色**：登录用户

请求体（可只传要改的字段）：

```json
{ "real_name": "新名字", "phone": "13900000000" }
```

**响应 200**（`data`）：更新后的 UserSerializer 结构。`username`/`role`/`id` 为只读，传了也不生效。

#### B4 · #6 修改密码

- **接口名**：修改密码
- `POST {{baseUrl}}/api/users/change-password/`
- **角色**：登录用户

请求体：

```json
{ "old_password": "old123456", "new_password": "new123456Aa" }
```

**响应 200**（`data` 为 null）：`{ "code": 0, "message": "密码修改成功", "data": null }`。

---

### 链路 C：组织（行政区 + 学校）

#### C1 · #7-#11 行政区 CRUD

- **接口名**：行政区 列表 / 新增 / 详情 / 修改 / 删除
- 路径与方法：

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/org/regions/` | 学校/区县/市州/省级 |
| POST | `/api/org/regions/` | 市州/省级 |
| GET | `/api/org/regions/{id}/` | 学校/区县/市州/省级 |
| PUT | `/api/org/regions/{id}/` | 市州/省级 |
| DELETE | `/api/org/regions/{id}/` | 仅省级 |

请求体（POST/PUT 相同）：

```json
{ "name": "武侯区", "code": "510107", "level": "district", "parent": 2 }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 名称 |
| `code` | string | 是 | 行政区代码（唯一） |
| `level` | string | 是 | province/city/district |
| `parent` | number | 否 | 上级行政区 id |

**响应**（`data`，单条 Region）：

```json
{
  "id": 4,
  "name": "武侯区",
  "code": "510107",
  "level": "district",
  "parent": 2,
  "created_at": "2026-10-22T20:00:00+08:00",
  "updated_at": "2026-10-22T20:00:00+08:00",
  "is_deleted": false,
  "deleted_at": null
}
```

列表查询参数：`?level=district`（按层级过滤）。列表返回 `data.list` + `data.total`。
DELETE 返回 `{ "code": 0, "message": "删除成功", "data": null }`（软删除）。

#### C2 · #12-#16 学校 CRUD

- **接口名**：学校 列表 / 新增 / 详情 / 修改 / 删除
- 路径与方法：`/api/org/schools/`（前缀 org），角色统一为 区县/市州/省级

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/org/schools/` | 区县/市州/省级 |
| POST | `/api/org/schools/` | 区县/市州/省级 |
| GET | `/api/org/schools/{id}/` | 区县/市州/省级 |
| PUT | `/api/org/schools/{id}/` | 区县/市州/省级 |
| DELETE | `/api/org/schools/{id}/` | 区县/市州/省级 |

请求体（POST/PUT）：

```json
{ "name": "测试中学", "code": "SCH002", "region": 3, "address": "某路2号", "contact": "王主任", "phone": "028-88888888" }
```

**响应**（`data`，单条 School）：

```json
{
  "id": 2,
  "name": "测试中学",
  "code": "SCH002",
  "region": 3,
  "address": "某路2号",
  "contact": "王主任",
  "phone": "028-88888888",
  "region_name": "锦江区"
}
```

列表查询参数：`?region=3`（按行政区过滤）。

---

### 链路 D：班级（CRUD + 学生/教师业务操作）

#### D1 · #17-#21 班级 CRUD

- **接口名**：班级 列表 / 新增 / 详情 / 修改 / 解散
- 路径与方法：`/api/classroom/classes/`

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/classroom/classes/` | 教师/学校 |
| POST | `/api/classroom/classes/` | 教师/学校 |
| GET | `/api/classroom/classes/{id}/` | 学生/教师/学校 |
| PUT | `/api/classroom/classes/{id}/` | 教师/学校 |
| DELETE | `/api/classroom/classes/{id}/` | 教师/学校 |

请求体（POST/PUT）：

```json
{ "name": "四年级二班", "code": "CLS002", "grade": "四年级", "school": 1, "head_teacher": 2 }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 班级名 |
| `code` | string | 是 | 班级编号（唯一） |
| `grade` | string | 否 | 年级 |
| `school` | number | 是 | 所属学校 id |
| `head_teacher` | number | 否 | 班主任 user id（教师创建时留空会自动设为本人） |

**响应**（`data`，单条 ClassRoom）：

```json
{
  "id": 2,
  "name": "四年级二班",
  "code": "CLS002",
  "grade": "四年级",
  "school": 1,
  "head_teacher": 2,
  "school_name": "测试小学",
  "head_teacher_name": "李老师"
}
```

列表查询参数：`?school=1`。

#### D2 · #22 学生申请加入班级

- **接口名**：学生申请加入班级
- `POST {{baseUrl}}/api/classroom/classes/{id}/join/`
- **角色**：学生

请求体（可空对象）：

```json
{ "student_no": "S2024001" }
```

**响应 201**（`data`，ClassStudent）：

```json
{
  "id": 1,
  "klass": 2,
  "student": 4,
  "status": "pending",
  "student_username": "student",
  "student_real_name": "小明"
}
```

**验证**：`status = pending`（待审核）。重复申请会返回业务错误（已待审核 / 已是成员）。

#### D3 · #23 学生退出班级

- **接口名**：学生退出班级
- `POST {{baseUrl}}/api/classroom/classes/{id}/quit/`
- **角色**：学生

**请求体**：无

**响应 200**：`{ "code": 0, "message": "已退出班级", "data": null }`。

#### D4 · #24 学生申请换班

- **接口名**：学生申请换班
- `POST {{baseUrl}}/api/classroom/classes/{id}/change/`
- **角色**：学生

请求体：

```json
{ "target_class_id": 2, "reason": "搬家" }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `target_class_id` | number | 是 | 目标班级 id |
| `reason` | string | 否 | 换班原因 |

**响应 201**（`data`）：目标班级的新 ClassStudent（status=pending）。

#### D5 · #25 教师审核学生申请

- **接口名**：审核学生入班申请
- `POST {{baseUrl}}/api/classroom/classes/{id}/students/{sid}/approve/`
- **角色**：教师（该班班主任或已通过科任教师）

请求体：

```json
{ "approved": true }
```

**响应 200**（`data`）：更新后的 ClassStudent（status=approved 或 rejected）。

#### D6 · #26 班主任审核科任教师

- **接口名**：审核科任教师申请
- `POST {{baseUrl}}/api/classroom/classes/{id}/teachers/{tid}/approve/`
- **角色**：教师（仅该班班主任）

请求体：

```json
{ "approved": true }
```

**响应 200**（`data`）：更新后的 ClassTeacher（status=approved 或 rejected）。

#### D7 · #27 批量导入学生

- **接口名**：批量导入学生入班
- `POST {{baseUrl}}/api/classroom/classes/{id}/students/import/`
- **角色**：教师/学校

请求体（`student_ids` 和 `student_nos` 至少传一个）：

```json
{ "student_ids": [4], "student_nos": ["S2024001"] }
```

**响应 200**（`data`）：

```json
{ "created": 0, "skipped": 1, "total": 1 }
```

#### D8 · 补充：教师申请担任科任教师

- **接口名**：教师申请加入班级（科任教师）
- `POST {{baseUrl}}/api/classroom/classes/{id}/join-teacher/`
- **角色**：教师

**请求体**：无

**响应 201**（`data`，ClassTeacher）：

```json
{
  "id": 1,
  "klass": 2,
  "teacher": 2,
  "course": null,
  "status": "pending",
  "teacher_username": "teacher",
  "teacher_real_name": "李老师",
  "course_name": ""
}
```

> 完整闭环：D8 科任教师申请 → 班主任用 D6 审核通过。

---

### 链路 E：账号管理（role 参数化 User 管理）

#### E1 · #28-#32 账号 CRUD

- **接口名**：账号 列表 / 新增 / 详情 / 修改 / 删除
- 路径与方法：`/api/accounts/`（注意：无 id 时是集合，带 id 是单条）

| 方法 | 路径 | 角色 |
| --- | --- | --- |
| GET | `/api/accounts/` | 学校/区县/市州/省级 |
| POST | `/api/accounts/` | 学校/区县/市州/省级 |
| GET | `/api/accounts/{id}/` | 学校/区县/市州/省级 |
| PUT | `/api/accounts/{id}/` | 学校/区县/市州/省级 |
| DELETE | `/api/accounts/{id}/` | 学校/区县/市州/省级 |

请求体（POST；`password` 可选，不传则不可登录）：

```json
{
  "username": "teacher02",
  "password": "pass12345Aa",
  "real_name": "张老师",
  "phone": "13800001111",
  "role": "teacher",
  "student_no": "",
  "school": 1,
  "region": 3
}
```

**响应**（`data`，AccountManageSerializer）：

```json
{
  "id": 11,
  "username": "teacher02",
  "real_name": "张老师",
  "phone": "13800001111",
  "avatar": "",
  "role": "teacher",
  "student_no": "",
  "school": 1,
  "region": 3,
  "email": "",
  "is_active": true,
  "date_joined": "2026-10-22T20:00:00+08:00"
}
```

列表查询参数：`?role=teacher`、`?keyword=张`（模糊匹配 username/student_no/real_name）。
DELETE 为软删（`is_active=False`），返回 `{ "message": "删除成功", "data": null }`。

#### E2 · #33 重置账号密码

- **接口名**：重置指定账号密码
- `POST {{baseUrl}}/api/accounts/{id}/reset-password/`
- **角色**：学校/区县/市州/省级

请求体（可选，不传默认 123456）：

```json
{ "new_password": "reset12345Aa" }
```

**响应 200**（`data`）：

```json
{ "new_password": "reset12345Aa" }
```

#### E3 · #34 批量创建账号

- **接口名**：批量创建账号
- `POST {{baseUrl}}/api/accounts/batch-create/`
- **角色**：仅学校管理员

请求体：

```json
{ "role": "student", "prefix": "stu", "count": 3, "default_password": "123456", "school": 1, "region": 3, "real_names": ["甲", "乙", "丙"] }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `role` | string | 是 | 账号角色 |
| `prefix` | string | 是 | 用户名前缀 |
| `count` | number | 是 | 数量（1-500） |
| `default_password` | string | 否 | 默认 123456 |
| `school` / `region` | number | 否 | 归属 |
| `real_names` | array | 否 | 按序号对应真实姓名 |

**响应 200**（`data`）：

```json
{ "created": 3, "usernames": ["stu001", "stu002", "stu003"] }
```

#### E4 · #35 批量导入账号

- **接口名**：批量导入账号
- `POST {{baseUrl}}/api/accounts/batch-import/`
- **角色**：学校/省级

请求体：

```json
{
  "role": "student",
  "items": [
    { "username": "stu101", "password": "123456", "real_name": "张三", "student_no": "S2024101", "school": 1 },
    { "username": "stu102", "password": "123456", "real_name": "李四", "student_no": "S2024102", "school": 1 }
  ]
}
```

**响应 200**（`data`）：

```json
{ "created": 2, "skipped": 0, "errors": [] }
```

#### E5 · #36 查询学生身份材料

- **接口名**：查询学生身份材料
- `GET {{baseUrl}}/api/accounts/{id}/materials/`
- **角色**：教师/学校

**响应 200**（`data`）：

```json
{
  "user_id": 4,
  "username": "student",
  "real_name": "小明",
  "student_no": "S2024001",
  "phone": "",
  "school": "测试小学",
  "region": "锦江区",
  "classes": [
    { "class_id": 1, "class_name": "三年级一班", "class_code": "CLS001", "school_name": "测试小学" }
  ]
}
```

**验证**：传非学生 id → 返回业务错误（仅学生有身份材料）。

---

### 链路 F：操作日志（#37）

#### F1 · #37 操作日志列表

- **接口名**：系统操作日志查询
- `GET {{baseUrl}}/api/logs/`
- **角色**：仅省级 / 题库管理员

**请求参数**（全部可选）：`module`、`method`、`path`、`start_time`、`end_time`、`user_id`

**响应 200**（`data.list` 元素，OperationLog）：

```json
{
  "id": 1,
  "user": 1,
  "action": "",
  "module": "exam",
  "method": "POST",
  "path": "/api/exam/answer-sheets/",
  "ip": "127.0.0.1",
  "detail": null,
  "created_at": "2026-10-22T20:00:00+08:00"
}
```

**负向验证**：用 `teacher` 调 → 403（仅省级/题库管理员）。

---

## 五、负向 / 权限验证（建议做）

| 验证项 | 做法 | 预期 |
| --- | --- | --- |
| 学生不能删行政区 | `student` 调 `DELETE /api/org/regions/{id}/` | 403 |
| 区县不能删行政区 | `district` 调 `DELETE /api/org/regions/{id}/` | 403（仅省级） |
| 学生访问账号管理 | `student` 调 `GET /api/accounts/` | 403 |
| 教师访问操作日志 | `teacher` 调 `GET /api/logs/` | 403 |
| 学生重复加入班级 | 已 pending 再调 join | 400（已有待审核申请） |
| 非班主任审核科任教师 | 普通教师调 approve_teacher | 403（仅班主任） |

---

## 六、关键参数速查

### 6.1 seed 造出的 id 参考

| 资源 | 值 | 说明 |
| --- | --- | --- |
| 四川省 | id=1 | level=province |
| 成都市 | id=2 | level=city, parent=1 |
| 锦江区 | id=3 | level=district, parent=2 |
| 测试小学 | id=1 | region=3, code=SCH001 |
| 三年级一班 | id=1 | school=1, code=CLS001 |
| teacher | id=2 | 教师，school=1 |
| student | id=4 | 学生，school=1，student_no=S2024001 |

> 以上为当前开发库实际值；不确定时以接口返回为准（如 `GET /api/org/regions/`）。

### 6.2 角色权限速查

| 接口 | 允许角色 |
| --- | --- |
| Region 读 | 学校/区县/市州/省级 |
| Region 写(POST/PUT) | 市州/省级 |
| Region 删 | 仅省级 |
| School CRUD | 区县/市州/省级 |
| ClassRoom CRUD | 教师/学校 |
| ClassRoom 详情 | 学生/教师/学校 |
| join/quit/change | 学生 |
| approve_student/approve_teacher/join-teacher | 教师 |
| import_students | 教师/学校 |
| Account CRUD + reset-password | 学校/区县/市州/省级 |
| batch-create | 仅学校 |
| batch-import | 学校/省级 |
| materials | 教师/学校 |
| 日志 | 仅省级/题库管理员 |

---

## 七、常见问题排查

| 现象 | 原因与解决 |
| --- | --- |
| 启动报 `no such column: ..._deleted_at` | 迁移冲突，回看「1.1」 |
| 登录后请求 401 | token 取错，应是 `data.access`，Header `Authorization: Bearer {{access}}` |
| 注册报密码错误 | 密码需满足 Django 强度校验（≥8 位、非纯数字、非纯常见密码） |
| 403 Forbidden | 角色不对，见「6.2」权限矩阵 |
| 列表接口结构对不上 | 列表统一是 `data.list` + `data.total` |
| 删了资源却还在查得到 | 本系统是软删除，列表默认过滤 `is_deleted=false`，但已被软删的记录不在列表里（符合预期） |

---

## 附：完整接口路径速查

| # | 方法 | 路径 | 角色 |
| --- | --- | --- | --- |
| 1 | POST | `/api/auth/login/` | 公开 |
| 2 | POST | `/api/auth/refresh/` | 公开 |
| 3 | POST | `/api/users/register/` | 公开 |
| 4 | GET | `/api/users/me/` | 登录用户 |
| 5 | PUT | `/api/users/me/` | 登录用户 |
| 6 | POST | `/api/users/change-password/` | 登录用户 |
| 7 | GET | `/api/org/regions/` | 学校/区县/市州/省级 |
| 8 | POST | `/api/org/regions/` | 市州/省级 |
| 9 | GET | `/api/org/regions/{id}/` | 学校/区县/市州/省级 |
| 10 | PUT | `/api/org/regions/{id}/` | 市州/省级 |
| 11 | DELETE | `/api/org/regions/{id}/` | 仅省级 |
| 12 | GET | `/api/org/schools/` | 区县/市州/省级 |
| 13 | POST | `/api/org/schools/` | 区县/市州/省级 |
| 14 | GET | `/api/org/schools/{id}/` | 区县/市州/省级 |
| 15 | PUT | `/api/org/schools/{id}/` | 区县/市州/省级 |
| 16 | DELETE | `/api/org/schools/{id}/` | 区县/市州/省级 |
| 17 | GET | `/api/classroom/classes/` | 教师/学校 |
| 18 | POST | `/api/classroom/classes/` | 教师/学校 |
| 19 | GET | `/api/classroom/classes/{id}/` | 学生/教师/学校 |
| 20 | PUT | `/api/classroom/classes/{id}/` | 教师/学校 |
| 21 | DELETE | `/api/classroom/classes/{id}/` | 教师/学校 |
| 22 | POST | `/api/classroom/classes/{id}/join/` | 学生 |
| 23 | POST | `/api/classroom/classes/{id}/quit/` | 学生 |
| 24 | POST | `/api/classroom/classes/{id}/change/` | 学生 |
| 25 | POST | `/api/classroom/classes/{id}/students/{sid}/approve/` | 教师 |
| 26 | POST | `/api/classroom/classes/{id}/teachers/{tid}/approve/` | 教师(班主任) |
| 27 | POST | `/api/classroom/classes/{id}/students/import/` | 教师/学校 |
| + | POST | `/api/classroom/classes/{id}/join-teacher/` | 教师 |
| 28 | GET | `/api/accounts/` | 学校/区县/市州/省级 |
| 29 | POST | `/api/accounts/` | 学校/区县/市州/省级 |
| 30 | GET | `/api/accounts/{id}/` | 学校/区县/市州/省级 |
| 31 | PUT | `/api/accounts/{id}/` | 学校/区县/市州/省级 |
| 32 | DELETE | `/api/accounts/{id}/` | 学校/区县/市州/省级 |
| 33 | POST | `/api/accounts/{id}/reset-password/` | 学校/区县/市州/省级 |
| 34 | POST | `/api/accounts/batch-create/` | 仅学校 |
| 35 | POST | `/api/accounts/batch-import/` | 学校/省级 |
| 36 | GET | `/api/accounts/{id}/materials/` | 教师/学校 |
| 37 | GET | `/api/logs/` | 仅省级/题库管理员 |
