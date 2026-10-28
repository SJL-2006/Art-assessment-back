# 艺术测评系统 Apifox 接口测试步骤（完整版）

> 适用项目：艺术测评系统后端（Django 4.2 + DRF 3.14 + SimpleJWT）。
> 本文是 **全量接口** 的 Apifox 测试手册，合并原 A/B/C 三模块并补充新增接口（内容模块「趣味课堂知识」、班级测评信息、统计地区/市州维度、市直属学校标记）。
> 每个接口统一按同一模板编写：**接口编号、接口名称、请求方法、请求路径、请求头、权限角色、请求体 JSON、请求字段表、响应示例 JSON、响应字段表**。

---

## 1. 文档说明

### 1.1 接口总清单

本系统共 **115 个接口**，按资源分 15 组：

| 分组 | 接口编号 | 数量 | 说明 |
| --- | --- | --- | --- |
| 认证 | #1 - #2 | 2 | 登录、刷新令牌 |
| 用户 | #3 - #6 | 4 | 注册、当前用户查询/修改、修改密码 |
| 组织-行政区 | #7 - #11 | 5 | Region CRUD |
| 组织-学校 | #12 - #16 | 5 | School CRUD（含「市直属」标记） |
| 班级 | #17 - #28 | 12 | 班级 CRUD + 学生/教师业务操作 |
| 班级关系（只读） | #29 - #32 | 4 | 班级学生 / 班级教师列表与详情 |
| 账号管理 | #33 - #41 | 9 | 统一账号 CRUD + 批量/重置/材料 |
| 操作日志 | #42 | 1 | 系统日志查询 |
| 题库-课程 | #43 - #47 | 5 | Course CRUD |
| 题库-章节 | #48 - #52 | 5 | Chapter CRUD |
| 题库-试题 | #53 - #61 | 9 | Question CRUD + 资源 + 审核 |
| 试卷 | #62 - #70 | 9 | Paper CRUD + 自动组卷 + 暂存 + 下载 |
| 试卷-试题关联 | #71 - #75 | 5 | PaperQuestion CRUD |
| 试卷-发布 | #76 - #81 | 6 | PaperPublish CRUD + 撤回 |
| 答题 AI 评分 | #82 - #83 | 2 | 主观题 AI 评分（DeepSeek） |
| 测评作答 | #84 - #90 | 7 | 可作答列表 / 试卷详情 / 作答 / 保存 / 提交 / 记录 / 报告 |
| 学生端结果 | #91 - #95 | 5 | 我的成绩 / 曲线 / 成长 / 上传 / **班级测评信息** |
| 判分与评分 | #96 - #102 | 7 | 查看学生 / 平时评分 / 模板 / 导入 / 补录 / 导出 |
| 数据统计 | #103 - #105 | 3 | 测评统计 / 导出 / 参与率导出（含**地区/市州**维度） |
| 证书 | #106 - #110 | 5 | 我的证书 / 详情 / 下载 / 学生证书 / 导出 |
| 内容-趣味课堂知识 | #111 - #115 | 5 | FunClassKnowledge CRUD（**新增**） |

> 依赖关系：**组织/账号（#1-#42）** 是数据底座 → **题库/试卷（#43-#83）** 提供题目与测评 → **作答/判分/统计/证书/内容（#84-#115）** 面向学生与管理员。

---

## 2. 统一规范

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

分页查询参数：`?page=1`（页码）、`?page_size=20`（每页条数，最大 100）。

> 例外：`#91 我的成绩`、`#92 成绩曲线`、`#93 成长曲线`、`#95 班级测评信息`、`#97 查看学生成绩`、`#109 学生证书` 返回的数据**不分页**，直接放在 `data` 里。

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

除公开接口（#1 #2 #3）外，其余接口均需在请求头携带 JWT：

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

> 说明：`DecimalField`（`Question.score`、`Paper.total_score`、`PaperQuestion.score` 等）经 DRF 序列化后为字符串（如 `"5.00"`）；`answer_views.py`/`student_views.py`/`score_views.py`/`stats_views.py`/`certificate_views.py` 中多用 `float()`/`round()` 输出为 **number**。请以各接口响应字段表为准。

---

## 3. 前置准备

### 3.1 迁移与演示数据

```bash
python manage.py makemigrations --merge --noinput
python manage.py migrate
python manage.py seed_demo
```

`seed_demo` 幂等，造好完整数据链：

| 环节 | 内容 |
| --- | --- |
| 组织 | 四川省 → 成都市 → 锦江区 → 测试小学（SCH001） |
| 班级 | 三年级一班（CLS001） |
| 学生 | student（学号 S2024001），已入班并通过审核 |
| 教师 | teacher（李老师，归属测试小学） |
| 题库 | 音乐/美术课程、若干章节、4 道已审核客观题 |
| 试卷 | 三年级音乐正式测评（formal，总分 20，4 道客观题） |
| 发布 | scope=class 命中三年级一班，状态 published |

### 3.2 启动服务

```bash
python manage.py runserver 8000
```

验证：浏览器打开 `http://127.0.0.1:8000/api/docs/`（中文 Swagger）。

### 3.3 测试账号

| 账号 | 密码 | 角色 | 适合测试 |
| --- | --- | --- | --- |
| student | student123456 | 学生 | 作答、我的成绩、成长曲线、上传、我的证书、班级测评信息、趣味课堂（只读） |
| teacher | teacher123456 | 教师 | 班级 CRUD、审核、试题写、试卷、查看学生成绩、平时评分 |
| school | school123456 | 学校管理员 | 班级、账号管理、判分评分、统计 |
| district | district123456 | 区县管理员 | 学校 CRUD、账号、补录、统计 |
| city | city123456 | 市州管理员 | 行政区写、学校、账号、补录、统计 |
| province | province123456 | 省级管理员 | 行政区全部、日志、账号、统计、参与率导出、趣味课堂（维护） |
| admin | admin123456 | 题库管理员(超管) | 题库写/审核、日志、趣味课堂（维护）、兜底排查 |

### 3.4 演示数据 id 参考

| 资源 | id | 说明 |
| --- | --- | --- |
| 四川省 | 1 | level=province |
| 成都市 | 2 | level=city, parent=1 |
| 锦江区 | 3 | level=district, parent=2 |
| 测试小学 | 1 | region=3, code=SCH001 |
| 三年级一班 | 1 | school=1, code=CLS001 |
| teacher | 2 | 教师，school=1 |
| student | 4 | 学生，school=1，student_no=S2024001 |
| 音乐课程 | 1 | code=music |
| 三年级音乐正式测评 | 1 | formal，总分 20 |
| 发布记录 | 1 | scope=class，命中三年级一班 |

> 以上为当前开发库实际值，不确定时以接口返回为准（如 `GET /api/org/regions/`）。

---

## 4. Apifox 配置

### 4.1 导入接口

1. Apifox →「导入数据」→「OpenAPI / Swagger」→ 选择 `docs/schema.yml`。
2. 自动生成分组：认证 / 用户 / 组织 / 班级 / 账号 / 日志 / 题库 / 试卷 / 答卷 / 证书 / 内容。

> 不同步时重新生成：`python manage.py spectacular --file docs/schema.yml`；或浏览器打开 `http://127.0.0.1:8000/api/docs/`。

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
2. 在后置操作添加「提取变量」：表达式 `$.data.access` → 写入变量 `access`。

> 换角色 = 换账号重新登录 = 重新提取 token。建议建多个环境分别缓存各角色 token（student / teacher / school / district / city / province / admin）。

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
| access | string | JWT 访问令牌，放入 `Authorization: Bearer <access>` |
| refresh | string | JWT 刷新令牌，用于 #2 换取新令牌 |

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

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| refresh | string | 是 | 上次登录/刷新返回的 refresh 令牌 |

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

### 5.2 用户

#### 5.2.1 #3 用户注册

| 属性 | 值 |
| --- | --- |
| 接口名称 | 用户注册 |
| 请求方法 | POST |
| 请求路径 | /api/users/register/ |
| 请求头 | 无 |
| 权限角色 | 公开 |

**请求体**（application/json）

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

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | string | 是 | 登录账号（唯一） |
| password | string | 是 | 需过 Django 密码强度校验（≥8 位、非纯数字） |
| role | string | 否 | student/teacher/school/district/city/province/qb_admin，默认 student |
| real_name | string | 否 | 真实姓名 |
| phone | string | 否 | 手机号 |
| student_no | string | 否 | 学籍号 |
| school | integer | 否 | 所属学校 id |
| region | integer | 否 | 所属行政区 id |

**响应示例**（201）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
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
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 用户 id |
| username | string | 登录账号 |
| real_name | string | 真实姓名 |
| phone | string | 手机号 |
| avatar | string | 头像 URL（空字符串表示未设置） |
| role | string | 角色标识 |
| role_display | string | 角色中文名 |
| student_no | string | 学籍号 |
| school | integer | 所属学校 id（可为 null） |
| region | integer | 所属行政区 id（可为 null） |
| email | string | 邮箱 |
| date_joined | string(date-time) | 注册时间 |

#### 5.2.2 #4 查询当前用户

| 属性 | 值 |
| --- | --- |
| 接口名称 | 获取当前用户信息 |
| 请求方法 | GET |
| 请求路径 | /api/users/me/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 登录用户 |

**请求参数**：无

**响应示例**（200）：`data` 结构同 #3 注册响应。

#### 5.2.3 #5 修改当前用户

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改当前用户信息 |
| 请求方法 | PUT |
| 请求路径 | /api/users/me/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 登录用户 |

**请求体**（application/json，可只传要改的字段）

```json
{
  "real_name": "新名字",
  "phone": "13900000000",
  "email": "new@example.com"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| real_name | string | 否 | 真实姓名 |
| phone | string | 否 | 手机号 |
| email | string | 否 | 邮箱 |
| avatar | string | 否 | 头像 |

> `id`/`username`/`role`/`date_joined` 为只读，传了不生效。

**响应示例**（200）：`data` 为更新后的用户对象（结构同 #3）。

#### 5.2.4 #6 修改密码

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改密码 |
| 请求方法 | POST |
| 请求路径 | /api/users/change-password/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 登录用户 |

**请求体**（application/json）

```json
{
  "old_password": "old123456",
  "new_password": "new123456Aa"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| old_password | string | 是 | 原密码 |
| new_password | string | 是 | 新密码（需过强度校验） |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "密码修改成功",
  "data": null
}
```

---

### 5.3 组织-行政区（Region）

#### 5.3.1 #7 行政区列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 行政区列表 |
| 请求方法 | GET |
| 请求路径 | /api/org/regions/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校 / 区县 / 市州 / 省级 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| level | string | 否 | 层级过滤：province / city / district |
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
        "id": 3,
        "name": "锦江区",
        "code": "510104",
        "level": "district",
        "parent": 2,
        "created_at": "2026-10-22T20:00:00+08:00",
        "updated_at": "2026-10-22T20:00:00+08:00",
        "is_deleted": false,
        "deleted_at": null
      }
    ],
    "total": 3,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 行政区 id |
| name | string | 名称 |
| code | string | 行政区代码（唯一） |
| level | string | 层级：province/city/district |
| parent | integer/null | 上级行政区 id（省级为 null） |
| created_at | string(date-time) | 创建时间 |
| updated_at | string(date-time) | 更新时间 |
| is_deleted | boolean | 是否软删除 |
| deleted_at | string(date-time)/null | 删除时间 |

#### 5.3.2 #8 新增行政区

| 属性 | 值 |
| --- | --- |
| 接口名称 | 新增行政区 |
| 请求方法 | POST |
| 请求路径 | /api/org/regions/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 市州 / 省级 |

**请求体**（application/json）

```json
{
  "name": "武侯区",
  "code": "510107",
  "level": "district",
  "parent": 2
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| name | string | 是 | 名称 |
| code | string | 是 | 行政区代码（唯一） |
| level | string | 是 | 层级：province/city/district |
| parent | integer | 否 | 上级行政区 id |

**响应示例**（201）：`data` 为新建的行政区对象（结构同 #7 列表元素）。

#### 5.3.3 #9 行政区详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 行政区详情 |
| 请求方法 | GET |
| 请求路径 | /api/org/regions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）：`data` 为单个行政区对象（结构同 #7）。

#### 5.3.4 #10 修改行政区

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改行政区 |
| 请求方法 | PUT |
| 请求路径 | /api/org/regions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 市州 / 省级 |

**请求体**（application/json，同 #8）

**响应示例**（200）：`data` 为更新后的行政区对象。

#### 5.3.5 #11 删除行政区

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除行政区 |
| 请求方法 | DELETE |
| 请求路径 | /api/org/regions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅省级 |

**请求体**：无

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

### 5.4 组织-学校（School）

#### 5.4.1 #12 学校列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 学校列表 |
| 请求方法 | GET |
| 请求路径 | /api/org/schools/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 区县 / 市州 / 省级 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| region | integer | 否 | 按行政区 id 过滤 |
| directly_affiliated | string | 否 | 按是否市直属过滤：`1` / `true` / `True`（仅返回市直属学校） |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 1,
        "name": "测试小学",
        "code": "SCH001",
        "region": 3,
        "address": "",
        "contact": "",
        "phone": "",
        "is_directly_affiliated": false,
        "region_name": "锦江区",
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
| id | integer | 学校 id |
| name | string | 学校名称 |
| code | string | 学校代码（唯一） |
| region | integer/null | 所属区县 id |
| address | string | 地址 |
| contact | string | 联系人 |
| phone | string | 联系电话 |
| is_directly_affiliated | boolean | 是否市直属（**新增字段**，默认 false） |
| region_name | string | 所属区县名称（只读冗余） |

#### 5.4.2 #13 新增学校

| 属性 | 值 |
| --- | --- |
| 接口名称 | 新增学校 |
| 请求方法 | POST |
| 请求路径 | /api/org/schools/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 区县 / 市州 / 省级 |

**请求体**（application/json）

```json
{
  "name": "测试中学",
  "code": "SCH002",
  "region": 3,
  "address": "某路 2 号",
  "contact": "王主任",
  "phone": "028-88888888",
  "is_directly_affiliated": true
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| name | string | 是 | 学校名称 |
| code | string | 是 | 学校代码（唯一） |
| region | integer | 否 | 所属区县 id |
| address | string | 否 | 地址 |
| contact | string | 否 | 联系人 |
| phone | string | 否 | 联系电话 |
| is_directly_affiliated | boolean | 否 | 是否市直属，默认 false |

**响应示例**（201）：`data` 为新建学校对象（结构同 #12）。

#### 5.4.3 #14 学校详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 学校详情 |
| 请求方法 | GET |
| 请求路径 | /api/org/schools/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 区县 / 市州 / 省级 |

**响应示例**（200）：`data` 为单个学校对象（结构同 #12）。

#### 5.4.4 #15 修改学校

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改学校 |
| 请求方法 | PUT |
| 请求路径 | /api/org/schools/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 区县 / 市州 / 省级 |

**请求体**（application/json，同 #13）

**响应示例**（200）：`data` 为更新后的学校对象。

#### 5.4.5 #16 删除学校

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除学校 |
| 请求方法 | DELETE |
| 请求路径 | /api/org/schools/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 区县 / 市州 / 省级 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

### 5.5 班级（ClassRoom）

#### 5.5.1 #17 班级列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 班级列表 |
| 请求方法 | GET |
| 请求路径 | /api/classroom/classes/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| school | integer | 否 | 按学校 id 过滤 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 1,
        "name": "三年级一班",
        "code": "CLS001",
        "grade": "三年级",
        "school": 1,
        "head_teacher": 2,
        "school_name": "测试小学",
        "head_teacher_name": "李老师",
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
| id | integer | 班级 id |
| name | string | 班级名称 |
| code | string | 班级编号（唯一） |
| grade | string | 年级 |
| school | integer | 所属学校 id |
| head_teacher | integer/null | 班主任 user id |
| school_name | string | 所属学校名称 |
| head_teacher_name | string | 班主任姓名 |

#### 5.5.2 #18 新增班级

| 属性 | 值 |
| --- | --- |
| 接口名称 | 新增班级 |
| 请求方法 | POST |
| 请求路径 | /api/classroom/classes/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**请求体**（application/json）

```json
{
  "name": "四年级二班",
  "code": "CLS002",
  "grade": "四年级",
  "school": 1,
  "head_teacher": 2
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| name | string | 是 | 班级名称 |
| code | string | 是 | 班级编号（唯一） |
| grade | string | 否 | 年级 |
| school | integer | 是 | 所属学校 id |
| head_teacher | integer | 否 | 班主任 user id（教师创建时留空自动设为本人） |

**响应示例**（201）：`data` 为新建班级对象（结构同 #17）。

#### 5.5.3 #19 班级详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 班级详情 |
| 请求方法 | GET |
| 请求路径 | /api/classroom/classes/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 / 教师 / 学校 |

**响应示例**（200）：`data` 为单个班级对象（结构同 #17）。

#### 5.5.4 #20 修改班级

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改班级 |
| 请求方法 | PUT |
| 请求路径 | /api/classroom/classes/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**请求体**（application/json，同 #18）

**响应示例**（200）：`data` 为更新后的班级对象。

#### 5.5.5 #21 解散班级

| 属性 | 值 |
| --- | --- |
| 接口名称 | 解散班级 |
| 请求方法 | DELETE |
| 请求路径 | /api/classroom/classes/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

#### 5.5.6 #22 学生申请加入班级

| 属性 | 值 |
| --- | --- |
| 接口名称 | 学生申请加入班级 |
| 请求方法 | POST |
| 请求路径 | /api/classroom/classes/{id}/join/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 |

**请求体**（application/json）

```json
{
  "student_no": "S2024001"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| student_no | string | 否 | 学籍号（供校验，可省略） |

**响应示例**（201）

```json
{
  "code": 0,
  "message": "申请已提交",
  "data": {
    "id": 1,
    "klass": 2,
    "student": 4,
    "status": "pending",
    "student_username": "student",
    "student_real_name": "小明",
    "created_at": "2026-10-22T20:00:00+08:00",
    "updated_at": "2026-10-22T20:00:00+08:00",
    "is_deleted": false,
    "deleted_at": null
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 关系记录 id |
| klass | integer | 班级 id |
| student | integer | 学生 user id |
| status | string | 状态：pending/approved/rejected |
| student_username | string | 学生账号 |
| student_real_name | string | 学生姓名 |

> 重复申请：已通过 → `你已是该班级成员`；待审核 → `已有待审核申请`；已拒绝 → 重新提交申请。

#### 5.5.7 #23 学生退出班级

| 属性 | 值 |
| --- | --- |
| 接口名称 | 学生退出班级 |
| 请求方法 | POST |
| 请求路径 | /api/classroom/classes/{id}/quit/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 |

**请求体**：无

**响应示例**（200）

```json
{
  "code": 0,
  "message": "已退出班级",
  "data": null
}
```

#### 5.5.8 #24 学生申请换班

| 属性 | 值 |
| --- | --- |
| 接口名称 | 学生申请换班 |
| 请求方法 | POST |
| 请求路径 | /api/classroom/classes/{id}/change/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 |

**请求体**（application/json）

```json
{
  "target_class_id": 2,
  "reason": "搬家"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| target_class_id | integer | 是 | 目标班级 id |
| reason | string | 否 | 换班原因 |

**响应示例**（201）：`data` 为目标班级的新 ClassStudent（status=pending，结构同 #22）。

#### 5.5.9 #25 审核学生入班申请

| 属性 | 值 |
| --- | --- |
| 接口名称 | 审核学生入班申请 |
| 请求方法 | POST |
| 请求路径 | /api/classroom/classes/{id}/students/{sid}/approve/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师（该班班主任或已通过科任教师） |

**请求体**（application/json）

```json
{
  "approved": true
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| approved | boolean | 是 | true=通过，false=拒绝 |

**响应示例**（200）：`data` 为更新后的 ClassStudent（status=approved 或 rejected，结构同 #22）。

#### 5.5.10 #26 班主任审核科任教师

| 属性 | 值 |
| --- | --- |
| 接口名称 | 审核科任教师申请 |
| 请求方法 | POST |
| 请求路径 | /api/classroom/classes/{id}/teachers/{tid}/approve/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师（仅该班班主任） |

**请求体**（application/json）

```json
{
  "approved": true
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| approved | boolean | 是 | true=通过，false=拒绝 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "已通过科任教师申请",
  "data": {
    "id": 1,
    "klass": 2,
    "teacher": 2,
    "course": null,
    "status": "approved",
    "teacher_username": "teacher",
    "teacher_real_name": "李老师",
    "course_name": ""
  }
}
```

#### 5.5.11 #27 批量导入学生

| 属性 | 值 |
| --- | --- |
| 接口名称 | 批量导入学生入班 |
| 请求方法 | POST |
| 请求路径 | /api/classroom/classes/{id}/students/import/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**请求体**（application/json，`student_ids` 与 `student_nos` 至少传一个）

```json
{
  "student_ids": [4],
  "student_nos": ["S2024001"]
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| student_ids | array(integer) | 否 | 学生 user id 列表 |
| student_nos | array(string) | 否 | 学籍号列表 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "导入完成：成功 1 人，跳过 0 人",
  "data": {
    "created": 1,
    "skipped": 0,
    "total": 1
  }
}
```

#### 5.5.12 #28 教师申请担任科任教师

| 属性 | 值 |
| --- | --- |
| 接口名称 | 教师申请加入班级（科任教师） |
| 请求方法 | POST |
| 请求路径 | /api/classroom/classes/{id}/join-teacher/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 |

**请求体**：无

**响应示例**（201）

```json
{
  "code": 0,
  "message": "科任教师申请已提交",
  "data": {
    "id": 1,
    "klass": 2,
    "teacher": 2,
    "course": null,
    "status": "pending",
    "teacher_username": "teacher",
    "teacher_real_name": "李老师",
    "course_name": ""
  }
}
```

> 完整闭环：#28 科任教师申请 → 班主任用 #26 审核通过。

---

### 5.6 班级关系（只读）

#### 5.6.1 #29 班级学生列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 班级学生列表 |
| 请求方法 | GET |
| 请求路径 | /api/classroom/class-students/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 学生 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| class | integer | 否 | 按班级 id 过滤 |

**响应示例**（200）：`data.list` 元素为 ClassStudent（结构同 #22，仅 status=approved 的记录）。

#### 5.6.2 #30 班级学生详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 班级学生详情 |
| 请求方法 | GET |
| 请求路径 | /api/classroom/class-students/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 学生 |

**响应示例**（200）：`data` 为单个 ClassStudent。

#### 5.6.3 #31 班级教师列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 班级教师列表 |
| 请求方法 | GET |
| 请求路径 | /api/classroom/class-teachers/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| class | integer | 否 | 按班级 id 过滤 |

**响应示例**（200）：`data.list` 元素为 ClassTeacher（结构同 #26，仅 status=approved）。

#### 5.6.4 #32 班级教师详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 班级教师详情 |
| 请求方法 | GET |
| 请求路径 | /api/classroom/class-teachers/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**响应示例**（200）：`data` 为单个 ClassTeacher。

---

### 5.7 账号管理（Account）

#### 5.7.1 #33 账号列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 账号列表 |
| 请求方法 | GET |
| 请求路径 | /api/accounts/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校 / 区县 / 市州 / 省级 |

**请求参数**（Query）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| role | string | 否 | 按角色过滤 |
| keyword | string | 否 | 模糊匹配 username/student_no/real_name |
| directly_affiliated | string | 否 | 按是否市直属过滤：`1` / `true` / `True`（返回所属学校为市直属的账号，用于市州端查市直属学校账号） |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
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
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 账号 id |
| username | string | 登录账号 |
| real_name | string | 真实姓名 |
| phone | string | 手机号 |
| avatar | string | 头像 URL |
| role | string | 角色标识 |
| student_no | string | 学籍号 |
| school | integer/null | 所属学校 id |
| region | integer/null | 所属行政区 id |
| email | string | 邮箱 |
| is_active | boolean | 是否启用（软删标志） |
| date_joined | string(date-time) | 创建时间 |

#### 5.7.2 #34 创建账号

| 属性 | 值 |
| --- | --- |
| 接口名称 | 创建账号 |
| 请求方法 | POST |
| 请求路径 | /api/accounts/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json）

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

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | string | 是 | 登录账号（唯一） |
| password | string | 否 | 密码（不传则不可登录） |
| real_name | string | 否 | 真实姓名 |
| phone | string | 否 | 手机号 |
| role | string | 是 | 角色：student/teacher/school/district/city/province/qb_admin |
| student_no | string | 否 | 学籍号 |
| school | integer | 否 | 所属学校 id |
| region | integer | 否 | 所属行政区 id |
| email | string | 否 | 邮箱 |

**响应示例**（201）：`data` 为新建账号对象（结构同 #33）。

#### 5.7.3 #35 账号详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 账号详情 |
| 请求方法 | GET |
| 请求路径 | /api/accounts/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）：`data` 为单个账号对象（结构同 #33）。

#### 5.7.4 #36 修改账号

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改账号 |
| 请求方法 | PUT |
| 请求路径 | /api/accounts/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json，同 #34，可部分字段）

**响应示例**（200）：`data` 为更新后的账号对象。

#### 5.7.5 #37 删除账号

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除账号 |
| 请求方法 | DELETE |
| 请求路径 | /api/accounts/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

> 软删实现：`is_active=False`。

#### 5.7.6 #38 重置账号密码

| 属性 | 值 |
| --- | --- |
| 接口名称 | 重置指定账号密码 |
| 请求方法 | POST |
| 请求路径 | /api/accounts/{id}/reset-password/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json，可省略则默认 123456）

```json
{
  "new_password": "reset12345Aa"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| new_password | string | 否 | 新密码，默认 `123456` |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "密码已重置",
  "data": {
    "new_password": "reset12345Aa"
  }
}
```

#### 5.7.7 #39 批量创建账号

| 属性 | 值 |
| --- | --- |
| 接口名称 | 批量创建账号 |
| 请求方法 | POST |
| 请求路径 | /api/accounts/batch-create/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学校 |

**请求体**（application/json）

```json
{
  "role": "student",
  "prefix": "stu",
  "count": 3,
  "default_password": "123456",
  "school": 1,
  "region": 3,
  "real_names": ["甲", "乙", "丙"]
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| role | string | 是 | 账号角色 |
| prefix | string | 是 | 用户名前缀，生成 `{prefix}{i:03d}` |
| count | integer | 是 | 数量（1-500） |
| default_password | string | 否 | 默认密码，默认 `123456` |
| school | integer | 否 | 归属学校 id |
| region | integer | 否 | 归属行政区 id |
| real_names | array(string) | 否 | 按序号对应真实姓名 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "批量创建完成，成功 3 个",
  "data": {
    "created": 3,
    "usernames": ["stu001", "stu002", "stu003"]
  }
}
```

#### 5.7.8 #40 批量导入账号

| 属性 | 值 |
| --- | --- |
| 接口名称 | 批量导入账号 |
| 请求方法 | POST |
| 请求路径 | /api/accounts/batch-import/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校 / 省级 |

**请求体**（application/json）

```json
{
  "role": "student",
  "items": [
    { "username": "stu101", "password": "123456", "real_name": "张三", "student_no": "S2024101", "school": 1 },
    { "username": "stu102", "password": "123456", "real_name": "李四", "student_no": "S2024102", "school": 1 }
  ]
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| role | string | 是 | 账号角色 |
| items | array(object) | 是 | 账号数组，每项含 username/password/real_name/phone/student_no/school/region |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "导入完成：成功 2 个，跳过 0 个",
  "data": {
    "created": 2,
    "skipped": 0,
    "errors": []
  }
}
```

#### 5.7.9 #41 查询学生身份材料

| 属性 | 值 |
| --- | --- |
| 接口名称 | 查询学生身份材料 |
| 请求方法 | GET |
| 请求路径 | /api/accounts/{id}/materials/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user_id": 4,
    "username": "student",
    "real_name": "小明",
    "student_no": "S2024001",
    "phone": "",
    "school": "测试小学",
    "region": "锦江区",
    "classes": [
      {
        "class_id": 1,
        "class_name": "三年级一班",
        "class_code": "CLS001",
        "school_name": "测试小学"
      }
    ]
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| user_id | integer | 学生 id |
| username | string | 学生账号 |
| real_name | string | 姓名 |
| student_no | string | 学籍号 |
| phone | string | 手机号 |
| school | string | 学校名称 |
| region | string | 行政区名称 |
| classes | array(object) | 已通过审核的班级列表 |

> 传非学生 id → 返回错误「仅学生有身份材料」。

---

### 5.8 操作日志

#### 5.8.1 #42 操作日志列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 系统操作日志查询 |
| 请求方法 | GET |
| 请求路径 | /api/logs/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅省级 / 题库管理员 |

**请求参数**（Query，全部可选）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| module | string | 否 | 模块名（users/org/classroom/exam 等） |
| method | string | 否 | HTTP 方法（GET/POST/PUT/DELETE） |
| path | string | 否 | 路径关键字模糊匹配 |
| start_time | string(date-time) | 否 | 起始时间 |
| end_time | string(date-time) | 否 | 结束时间 |
| user_id | integer | 否 | 操作人 id |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
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
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 日志 id |
| user | integer/null | 操作人 user id |
| action | string | 操作类型 |
| module | string | 模块 |
| method | string | 请求方法 |
| path | string | 请求路径 |
| ip | string/null | 来源 IP |
| detail | object/null | 详情 JSON |
| created_at | string(date-time) | 操作时间 |

---

### 5.9 题库-课程（Course）

#### 5.9.1 #43 课程列表

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

#### 5.9.2 #44 新增课程

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

**响应示例**（201）：`data` 为新建课程对象（结构同 #43）。

#### 5.9.3 #45 课程详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 课程详情 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/courses/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 / 教师 / 题库管理员 |

**响应示例**（200）：`data` 为单个课程对象（结构同 #43）。

#### 5.9.4 #46 修改课程

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改课程 |
| 请求方法 | PUT |
| 请求路径 | /api/questionbank/courses/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**请求体**（application/json，同 #44）

**响应示例**（200）：`data` 为更新后的课程对象。

#### 5.9.5 #47 删除课程

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

### 5.10 题库-章节（Chapter）

#### 5.10.1 #48 章节列表

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

#### 5.10.2 #49 新增章节

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

**响应示例**（201）：`data` 为新建章节对象（结构同 #48）。

#### 5.10.3 #50 章节详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 章节详情 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/chapters/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 / 教师 / 题库管理员 |

**响应示例**（200）：`data` 为单个章节对象（结构同 #48）。

#### 5.10.4 #51 修改章节

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改章节 |
| 请求方法 | PUT |
| 请求路径 | /api/questionbank/chapters/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅题库管理员 |

**请求体**（application/json，同 #49）

**响应示例**（200）：`data` 为更新后的章节对象。

#### 5.10.5 #52 删除章节

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

### 5.11 题库-试题（Question）

#### 5.11.1 #53 试题列表

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

#### 5.11.2 #54 新增试题

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

**响应示例**（201）：`data` 为新建试题对象（结构同 #53）。

#### 5.11.3 #55 试题详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试题详情 |
| 请求方法 | GET |
| 请求路径 | /api/questionbank/questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 题库管理员 |

**响应示例**（200）：`data` 为单个试题对象（结构同 #53）。

#### 5.11.4 #56 修改试题

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改试题 |
| 请求方法 | PUT |
| 请求路径 | /api/questionbank/questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 题库管理员 |

**请求体**（application/json，同 #54）

**响应示例**（200）：`data` 为更新后的试题对象。

#### 5.11.5 #57 删除试题

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

#### 5.11.6 #58 上传试题资源

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

#### 5.11.7 #59 删除试题资源

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

#### 5.11.8 #60 审核试题

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

#### 5.11.9 #61 查看审核记录

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

### 5.12 试卷（Paper）

#### 5.12.1 #62 试卷列表

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

#### 5.12.2 #63 新增试卷

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

**响应示例**（201）：`data` 为新建试卷对象（结构同 #62）。

#### 5.12.3 #64 试卷详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试卷详情 |
| 请求方法 | GET |
| 请求路径 | /api/exam/papers/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）：`data` 为单个试卷对象（结构同 #62，列表接口返回基础结构）。

#### 5.12.4 #65 修改试卷

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改试卷 |
| 请求方法 | PUT |
| 请求路径 | /api/exam/papers/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json，同 #63）

**响应示例**（200）：`data` 为更新后的试卷对象。

#### 5.12.5 #66 删除试卷

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

#### 5.12.6 #67 自动组卷

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
| title / ptype / subject / level / grade / duration / status / creator | — | 同 #62 |
| total_score | string(decimal) | 总分 |
| question_count | integer | 题目数量 |
| paper_questions | array(object) | 已关联题目，每项含 `question`（完整题目）、`sort`（题号）、`score`（分值） |

#### 5.12.7 #68 暂存（草稿）组卷

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

**响应示例**（200）：`data` 为 PaperDetail（结构同 #67，含 paper_questions）。

#### 5.12.8 #69 下载试卷材料（zip）

| 属性 | 值 |
| --- | --- |
| 接口名称 | 下载试卷材料包 |
| 请求方法 | GET |
| 请求路径 | /api/exam/papers/{id}/materials/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应**（200）：二进制文件流 `application/zip`，内容为试卷内题目的音频/图片资源压缩包。

#### 5.12.9 #70 下载试卷答案（txt）

| 属性 | 值 |
| --- | --- |
| 接口名称 | 下载试卷答案 |
| 请求方法 | GET |
| 请求路径 | /api/exam/papers/{id}/answers/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应**（200）：文本流 `text/plain; charset=utf-8`，逐题列出答案与解析。

---

### 5.13 试卷-试题关联（PaperQuestion）

#### 5.13.1 #71 试题关联列表

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

#### 5.13.2 #72 新增试题关联

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

**响应示例**（201）：`data` 为新建关联对象（结构同 #71）。

#### 5.13.3 #73 试题关联详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试卷试题关联详情 |
| 请求方法 | GET |
| 请求路径 | /api/exam/paper-questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）：`data` 为单个关联对象（结构同 #71）。

#### 5.13.4 #74 修改试题关联

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改试卷试题关联 |
| 请求方法 | PUT |
| 请求路径 | /api/exam/paper-questions/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json，同 #72）

**响应示例**（200）：`data` 为更新后的关联对象。

#### 5.13.5 #75 删除试题关联

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

> 一般用 #67/#68 自动关联，此接口供调整顺序/分值时用。

---

### 5.14 试卷-发布（PaperPublish）

#### 5.14.1 #76 发布记录列表

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

#### 5.14.2 #77 发布试卷

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

#### 5.14.3 #78 发布记录详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 发布记录详情 |
| 请求方法 | GET |
| 请求路径 | /api/exam/publishes/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**响应示例**（200）：`data` 为单个发布记录（结构同 #76）。

#### 5.14.4 #79 修改发布记录

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改发布记录 |
| 请求方法 | PUT |
| 请求路径 | /api/exam/publishes/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校 / 区县 / 市州 / 省级 |

**请求体**（application/json，同 #77）

**响应示例**（200）：`data` 为更新后的发布记录。

#### 5.14.5 #80 删除发布记录

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

#### 5.14.6 #81 撤回发布

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

### 5.15 答题 AI 评分（DeepSeek）

> 主观题 AI 评分，后端接入 DeepSeek（OpenAI 兼容接口）。后续将替换为算法实验室自研模型，接口签名不变。

#### 5.15.1 #82 AI 单卷评分

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

#### 5.15.2 #83 AI 批量评分

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

### 5.16 测评作答

#### 5.16.1 #84 我可作答的测评列表

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

#### 5.16.2 #85 试卷详情（含题目与资源）

| 属性 | 值 |
| --- | --- |
| 接口名称 | 试卷详情（含题目与资源） |
| 请求方法 | GET |
| 请求路径 | /api/exam/my-assessments/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

> `{id}` 为发布记录 id（来自 #84 的 `id` 字段）。**已提交才返回答案与解析**。

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

#### 5.16.3 #86 开始作答

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

#### 5.16.4 #87 保存答题进度

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

#### 5.16.5 #88 提交答卷（自动判分）

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

> 提交后正式测评达到及格线会自动发放证书（见 #106）。**限时测评到点未提交会被系统自动提交**（定时任务 + 统计接口兜底，见附录 6.6）。

#### 5.16.6 #89 我的测评记录

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

#### 5.16.7 #90 测评统计分析报告

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

### 5.17 学生端结果

#### 5.17.1 #91 我的成绩

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

#### 5.17.2 #92 成绩曲线

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
| points | array(object) | 成绩点（结构同 #91 的点，按时间升序） |
| total | integer | 成绩点数量 |

#### 5.17.3 #93 个人成长曲线

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
| series[].points | array(object) | 成绩点（结构同 #91 的点） |
| total | integer | 成绩点总数 |

#### 5.17.4 #94 上传课外自主学习图片

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

#### 5.17.5 #95 查看班级测评信息（**新增**）

| 属性 | 值 |
| --- | --- |
| 接口名称 | 查看班级测评信息 |
| 请求方法 | GET |
| 请求路径 | /api/exam/my-class/assessments/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**请求参数**（Query，全部可选）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| subject | string | 否 | 按学科过滤：music / art |
| keyword | string | 否 | 按测评名称 / 学科模糊搜索 |

**响应示例**（200，不分页）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "classes": [
      {
        "id": 1,
        "name": "三年级一班",
        "code": "CLS001",
        "school_name": "测试小学"
      }
    ],
    "assessments": [
      {
        "publish_id": 1,
        "paper_id": 1,
        "title": "三年级音乐正式测评",
        "subject": "music",
        "subject_display": "音乐",
        "ptype": "formal",
        "ptype_display": "正式测评",
        "grade": "三年级",
        "total_score": "20.00",
        "class_size": 2,
        "participant_count": 1,
        "average_score": "17.50",
        "pass_rate": 0.5,
        "end_at": null
      }
    ],
    "by_subject": [
      {
        "subject": "music",
        "subject_display": "音乐",
        "assessment_count": 1,
        "average_score": "17.50"
      }
    ],
    "total": 1
  }
}
```

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| classes | array(object) | 我所在的班级列表 |
| classes[].id / name / code / school_name | — | 班级 id/名称/编号/学校名 |
| assessments | array(object) | 各测评的班级级成绩汇总 |
| assessments[].publish_id / paper_id | integer | 发布/试卷 id |
| assessments[].title | string | 测评名称 |
| assessments[].subject / subject_display | string | 学科代码/中文 |
| assessments[].ptype / ptype_display | string | 类型代码/中文 |
| assessments[].grade | string | 年级 |
| assessments[].total_score | string(decimal) | 试卷总分 |
| assessments[].class_size | integer | 班级学生总数 |
| assessments[].participant_count | integer | 已提交答卷人数 |
| assessments[].average_score | string(decimal) | 班级平均分 |
| assessments[].pass_rate | number | 班级及格率（0-1） |
| assessments[].end_at | string(date-time)/null | 测评结束时间 |
| by_subject | array(object) | 按学科汇总 |
| by_subject[].subject / subject_display | string | 学科代码/中文 |
| by_subject[].assessment_count | integer | 测评数量 |
| by_subject[].average_score | string(decimal) | 学科平均分 |
| total | integer | 测评数量 |

---

### 5.18 判分与评分

#### 5.18.1 #96 查看学生课外学习材料

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

#### 5.18.2 #97 查看学生测评成绩

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

#### 5.18.3 #98 为学生平时表现评分

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

#### 5.18.4 #99 成绩导入模板下载

| 属性 | 值 |
| --- | --- |
| 接口名称 | 成绩导入模板下载 |
| 请求方法 | GET |
| 请求路径 | /api/exam/scores/template/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**响应**（200）：Excel 文件 `成绩导入模板.xlsx`（列：学籍号、姓名、班级编号、学科、分数、评语）。

#### 5.18.5 #100 导入学生线下成绩

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
| file | file | 是 | Excel 文件（按 #99 模板格式） |

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

#### 5.18.6 #101 测评成绩补录

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

#### 5.18.7 #102 导出学生所有成绩

| 属性 | 值 |
| --- | --- |
| 接口名称 | 导出学生所有成绩 |
| 请求方法 | GET |
| 请求路径 | /api/exam/students/{student_id}/scores/export/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**响应**（200）：Excel 文件 `<姓名>_成绩.xlsx`（列：类型、名称、学科、得分、满分、时间、评语）。

---

### 5.19 数据统计

#### 5.19.1 #103 测评数据统计（**含地区/市州维度**）

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

> 统计前会自动兜底提交已到期的未交答卷（`auto_submit_overdue_sheets`），避免超时未交导致漏统计。

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
    ],
    "by_region": [
      {
        "key": "锦江区",
        "label": "锦江区",
        "participant_count": 1,
        "submission_count": 1,
        "average_score_rate": 1.0,
        "pass_rate": 1.0
      }
    ],
    "by_city": [
      {
        "key": "成都市",
        "label": "成都市",
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
| by_subject / by_grade / by_school / by_region / by_city | array(object) | 分组统计（`by_region` 按区县、`by_city` 按市州为**新增维度**） |
| (组).key / label | string | 分组键/名称 |
| (组).participant_count / submission_count | integer | 参与人数/提交份数 |
| (组).average_score_rate / pass_rate | number | 平均得分率/及格率 |

#### 5.19.2 #104 统计导出 Excel

| 属性 | 值 |
| --- | --- |
| 接口名称 | 测评数据统计导出 |
| 请求方法 | GET |
| 请求路径 | /api/exam/stats/assessment/export/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学校管理员 / 区县管理员 / 市州管理员 / 省级管理员 |

**请求参数**：同 #103。

**响应**（200）：Excel 文件 `测评数据统计.xlsx`（含「学科/年级/学校/地区/市州」分组统计）。

#### 5.19.3 #105 测评参与率导出

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

### 5.20 证书

#### 5.20.1 #106 我的证书列表

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

#### 5.20.2 #107 证书详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 证书详情 |
| 请求方法 | GET |
| 请求路径 | /api/exam/certificates/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**响应示例**（200）：`data` 为单个证书对象（结构同 #106）。

#### 5.20.3 #108 下载证书

| 属性 | 值 |
| --- | --- |
| 接口名称 | 下载证书 |
| 请求方法 | GET |
| 请求路径 | /api/exam/certificates/{id}/download/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 仅学生 |

**响应**（200）：HTML 证书文件 `certificate_{id}.html`（无附件时自动生成）。

#### 5.20.4 #109 查看学生证书

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
| list | array(object) | 证书列表（结构同 #106） |
| total | integer | 证书数量 |

#### 5.20.5 #110 导出学生证书

| 属性 | 值 |
| --- | --- |
| 接口名称 | 导出学生证书 |
| 请求方法 | GET |
| 请求路径 | /api/exam/students/{student_id}/certificates/export/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 教师 / 学校管理员 |

**响应**（200）：Excel 文件 `<姓名>_证书.xlsx`（列：证书编号、证书名称、学科、关联测评、成绩、颁发时间）。

---

### 5.21 内容-趣味课堂知识（FunClassKnowledge，**新增**）

> 学生端素质教育展示。学生只读已发布内容；题库管理员 / 省级管理员可维护（CRUD）。

#### 5.21.1 #111 趣味课堂知识列表

| 属性 | 值 |
| --- | --- |
| 接口名称 | 趣味课堂知识列表 |
| 请求方法 | GET |
| 请求路径 | /api/content/knowledge/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 / 题库管理员 / 省级管理员 |

**请求参数**（Query，全部可选）

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| subject | string | 否 | 按学科过滤：music / art |
| search | string | 否 | 按标题模糊搜索 |
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页条数，默认 20 |

> 学生角色只返回 `is_published=true` 的内容；管理员可见全部。

**响应示例**（200）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": 1,
        "title": "有趣的五线谱",
        "subject": "music",
        "subject_display": "音乐",
        "content": "五线谱由五条平行横线组成……",
        "image": "http://127.0.0.1:8000/media/fun_class/2026/10/demo.png",
        "image_url": "http://127.0.0.1:8000/media/fun_class/2026/10/demo.png",
        "sort": 1,
        "is_published": true,
        "created_at": "2026-10-28T10:00:00+08:00",
        "updated_at": "2026-10-28T10:00:00+08:00"
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
| id | integer | 内容 id |
| title | string | 标题 |
| subject | string | 学科代码：music / art（可为空串） |
| subject_display | string | 学科中文名 |
| content | string | 正文内容 |
| image | string | 图片原始 URL（未上传为空串） |
| image_url | string | 图片完整 URL（未上传为空串） |
| sort | integer | 排序值（升序） |
| is_published | boolean | 是否发布 |
| created_at | string(date-time) | 创建时间 |
| updated_at | string(date-time) | 更新时间 |

#### 5.21.2 #112 新增趣味课堂知识

| 属性 | 值 |
| --- | --- |
| 接口名称 | 新增趣味课堂知识 |
| 请求方法 | POST |
| 请求路径 | /api/content/knowledge/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 题库管理员 / 省级管理员 |
| Content-Type | multipart/form-data（含图片时）/ application/json（不含图片时） |

**请求体**（multipart/form-data）

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| title | string | 是 | 标题（≤200 字符） |
| subject | string | 否 | 学科：music / art（空则不分学科） |
| content | string | 否 | 正文内容 |
| image | file | 否 | 图片文件 |
| sort | integer | 否 | 排序值，默认 0 |
| is_published | boolean | 否 | 是否发布，默认 true |

**响应示例**（201）：`data` 为新建内容对象（结构同 #111）。

#### 5.21.3 #113 趣味课堂知识详情

| 属性 | 值 |
| --- | --- |
| 接口名称 | 趣味课堂知识详情 |
| 请求方法 | GET |
| 请求路径 | /api/content/knowledge/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 学生 / 题库管理员 / 省级管理员 |

**响应示例**（200）：`data` 为单个内容对象（结构同 #111）。

#### 5.21.4 #114 修改趣味课堂知识

| 属性 | 值 |
| --- | --- |
| 接口名称 | 修改趣味课堂知识 |
| 请求方法 | PUT（或 PATCH 部分更新） |
| 请求路径 | /api/content/knowledge/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 题库管理员 / 省级管理员 |

**请求体**（同 #112，可部分字段）

**响应示例**（200）：`data` 为更新后的内容对象。

#### 5.21.5 #115 删除趣味课堂知识

| 属性 | 值 |
| --- | --- |
| 接口名称 | 删除趣味课堂知识 |
| 请求方法 | DELETE |
| 请求路径 | /api/content/knowledge/{id}/ |
| 请求头 | Authorization: Bearer {{access}} |
| 权限角色 | 题库管理员 / 省级管理员 |

**响应示例**（200）

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

> 软删除：`is_deleted=True` + `deleted_at` 记录时间，列表默认不再返回。

---

## 6. 附录

### 6.1 角色权限矩阵

| 接口域 | 允许角色 |
| --- | --- |
| 登录 / 刷新 / 注册 | 公开 |
| 用户 me / 改密 | 登录用户 |
| Region 读 | 学校 / 区县 / 市州 / 省级 |
| Region 写(POST/PUT) | 市州 / 省级 |
| Region 删 | 仅省级 |
| School CRUD | 区县 / 市州 / 省级 |
| ClassRoom CRUD | 教师 / 学校 |
| ClassRoom 详情 | 学生 / 教师 / 学校 |
| join / quit / change | 学生 |
| approve_student / approve_teacher / join-teacher | 教师 |
| import_students | 教师 / 学校 |
| 账号 CRUD + reset-password | 学校 / 区县 / 市州 / 省级 |
| batch-create | 仅学校 |
| batch-import | 学校 / 省级 |
| materials | 教师 / 学校 |
| 日志 | 仅省级 / 题库管理员 |
| 课程/章节 读 | 学生 / 教师 / 题库管理员 |
| 课程/章节 写 | 仅题库管理员 |
| 试题 CRUD + 资源 | 教师 / 题库管理员 |
| 试题审核 + 审核记录 | 仅题库管理员 |
| 试卷 / 发布 / 试题关联 | 教师 / 学校 / 区县 / 市州 / 省级 |
| AI 评分 | 教师 / 学校 |
| 作答 / 我的成绩 / 成长曲线 / 上传 / 我的证书 / 班级测评信息 | 学生 |
| 查看学生课外学习 / 成绩 / 平时评分 / 模板 / 导入 / 导出 / 证书查看 | 教师 / 学校管理员 |
| 成绩补录 | 学校管理员 / 区县管理员 / 市州管理员 |
| 测评统计 / 统计导出 | 学校管理员 / 区县管理员 / 市州管理员 / 省级管理员 |
| 参与率导出 | 仅省级管理员 |
| 趣味课堂知识 读 | 学生 / 题库管理员 / 省级管理员 |
| 趣味课堂知识 写 | 题库管理员 / 省级管理员 |

### 6.2 枚举值

| 字段 | 取值 |
| --- | --- |
| 角色 role | student / teacher / school / district / city / province / qb_admin |
| 行政区 level | province / city / district |
| 班级关系 status | pending / approved / rejected |
| qtype | single / multiple / judge / fill / short / listening / sight |
| difficulty | easy / medium / hard |
| 试题 status | draft / pending / approved / rejected |
| 科目 subject | music / art |
| ptype | practice / formal |
| 试卷 level | class / school / district / city / province |
| 发布 scope_type | class / school / grade / region |
| 发布 status | published / recalled |
| 资源 rtype | audio / image / video |
| 审核 result | approved / rejected |
| 成绩点 source | exam / daily |

### 6.3 接口路径速查

| # | 方法 | 路径 | 角色 |
| --- | --- | --- | --- |
| 1 | POST | /api/auth/login/ | 公开 |
| 2 | POST | /api/auth/refresh/ | 公开 |
| 3 | POST | /api/users/register/ | 公开 |
| 4 | GET | /api/users/me/ | 登录用户 |
| 5 | PUT | /api/users/me/ | 登录用户 |
| 6 | POST | /api/users/change-password/ | 登录用户 |
| 7 | GET | /api/org/regions/ | 学校/区县/市州/省级 |
| 8 | POST | /api/org/regions/ | 市州/省级 |
| 9 | GET | /api/org/regions/{id}/ | 学校/区县/市州/省级 |
| 10 | PUT | /api/org/regions/{id}/ | 市州/省级 |
| 11 | DELETE | /api/org/regions/{id}/ | 仅省级 |
| 12 | GET | /api/org/schools/ | 区县/市州/省级 |
| 13 | POST | /api/org/schools/ | 区县/市州/省级 |
| 14 | GET | /api/org/schools/{id}/ | 区县/市州/省级 |
| 15 | PUT | /api/org/schools/{id}/ | 区县/市州/省级 |
| 16 | DELETE | /api/org/schools/{id}/ | 区县/市州/省级 |
| 17 | GET | /api/classroom/classes/ | 教师/学校 |
| 18 | POST | /api/classroom/classes/ | 教师/学校 |
| 19 | GET | /api/classroom/classes/{id}/ | 学生/教师/学校 |
| 20 | PUT | /api/classroom/classes/{id}/ | 教师/学校 |
| 21 | DELETE | /api/classroom/classes/{id}/ | 教师/学校 |
| 22 | POST | /api/classroom/classes/{id}/join/ | 学生 |
| 23 | POST | /api/classroom/classes/{id}/quit/ | 学生 |
| 24 | POST | /api/classroom/classes/{id}/change/ | 学生 |
| 25 | POST | /api/classroom/classes/{id}/students/{sid}/approve/ | 教师 |
| 26 | POST | /api/classroom/classes/{id}/teachers/{tid}/approve/ | 教师(班主任) |
| 27 | POST | /api/classroom/classes/{id}/students/import/ | 教师/学校 |
| 28 | POST | /api/classroom/classes/{id}/join-teacher/ | 教师 |
| 29 | GET | /api/classroom/class-students/ | 教师/学校/学生 |
| 30 | GET | /api/classroom/class-students/{id}/ | 教师/学校/学生 |
| 31 | GET | /api/classroom/class-teachers/ | 教师/学校 |
| 32 | GET | /api/classroom/class-teachers/{id}/ | 教师/学校 |
| 33 | GET | /api/accounts/ | 学校/区县/市州/省级 |
| 34 | POST | /api/accounts/ | 学校/区县/市州/省级 |
| 35 | GET | /api/accounts/{id}/ | 学校/区县/市州/省级 |
| 36 | PUT | /api/accounts/{id}/ | 学校/区县/市州/省级 |
| 37 | DELETE | /api/accounts/{id}/ | 学校/区县/市州/省级 |
| 38 | POST | /api/accounts/{id}/reset-password/ | 学校/区县/市州/省级 |
| 39 | POST | /api/accounts/batch-create/ | 仅学校 |
| 40 | POST | /api/accounts/batch-import/ | 学校/省级 |
| 41 | GET | /api/accounts/{id}/materials/ | 教师/学校 |
| 42 | GET | /api/logs/ | 仅省级/题库管理员 |
| 43 | GET | /api/questionbank/courses/ | 学生/教师/题库管理员 |
| 44 | POST | /api/questionbank/courses/ | 仅题库管理员 |
| 45 | GET | /api/questionbank/courses/{id}/ | 学生/教师/题库管理员 |
| 46 | PUT | /api/questionbank/courses/{id}/ | 仅题库管理员 |
| 47 | DELETE | /api/questionbank/courses/{id}/ | 仅题库管理员 |
| 48 | GET | /api/questionbank/chapters/ | 学生/教师/题库管理员 |
| 49 | POST | /api/questionbank/chapters/ | 仅题库管理员 |
| 50 | GET | /api/questionbank/chapters/{id}/ | 学生/教师/题库管理员 |
| 51 | PUT | /api/questionbank/chapters/{id}/ | 仅题库管理员 |
| 52 | DELETE | /api/questionbank/chapters/{id}/ | 仅题库管理员 |
| 53 | GET | /api/questionbank/questions/ | 教师/题库管理员 |
| 54 | POST | /api/questionbank/questions/ | 教师/题库管理员 |
| 55 | GET | /api/questionbank/questions/{id}/ | 教师/题库管理员 |
| 56 | PUT | /api/questionbank/questions/{id}/ | 教师/题库管理员 |
| 57 | DELETE | /api/questionbank/questions/{id}/ | 教师/题库管理员 |
| 58 | POST | /api/questionbank/questions/{id}/resources/ | 教师/题库管理员 |
| 59 | DELETE | /api/questionbank/questions/{id}/resources/{rid}/ | 教师/题库管理员 |
| 60 | POST | /api/questionbank/questions/{id}/review/ | 仅题库管理员 |
| 61 | GET | /api/questionbank/questions/{id}/reviews/ | 仅题库管理员 |
| 62 | GET | /api/exam/papers/ | 教师/学校/区县/市州/省级 |
| 63 | POST | /api/exam/papers/ | 教师/学校/区县/市州/省级 |
| 64 | GET | /api/exam/papers/{id}/ | 教师/学校/区县/市州/省级 |
| 65 | PUT | /api/exam/papers/{id}/ | 教师/学校/区县/市州/省级 |
| 66 | DELETE | /api/exam/papers/{id}/ | 教师/学校/区县/市州/省级 |
| 67 | POST | /api/exam/papers/auto-generate/ | 教师/学校/区县/市州/省级 |
| 68 | POST | /api/exam/papers/{id}/draft/ | 教师/学校/区县/市州/省级 |
| 69 | GET | /api/exam/papers/{id}/materials/ | 教师/学校/区县/市州/省级 |
| 70 | GET | /api/exam/papers/{id}/answers/ | 教师/学校/区县/市州/省级 |
| 71 | GET | /api/exam/paper-questions/ | 教师/学校/区县/市州/省级 |
| 72 | POST | /api/exam/paper-questions/ | 教师/学校/区县/市州/省级 |
| 73 | GET | /api/exam/paper-questions/{id}/ | 教师/学校/区县/市州/省级 |
| 74 | PUT | /api/exam/paper-questions/{id}/ | 教师/学校/区县/市州/省级 |
| 75 | DELETE | /api/exam/paper-questions/{id}/ | 教师/学校/区县/市州/省级 |
| 76 | GET | /api/exam/publishes/ | 教师/学校/区县/市州/省级 |
| 77 | POST | /api/exam/publishes/ | 教师/学校/区县/市州/省级 |
| 78 | GET | /api/exam/publishes/{id}/ | 教师/学校/区县/市州/省级 |
| 79 | PUT | /api/exam/publishes/{id}/ | 教师/学校/区县/市州/省级 |
| 80 | DELETE | /api/exam/publishes/{id}/ | 教师/学校/区县/市州/省级 |
| 81 | POST | /api/exam/publishes/{id}/recall/ | 教师/学校/区县/市州/省级 |
| 82 | POST | /api/exam/answers/{id}/ai-grade/ | 教师/学校 |
| 83 | POST | /api/exam/answers/ai-grade-batch/ | 教师/学校 |
| 84 | GET | /api/exam/my-assessments/ | 学生 |
| 85 | GET | /api/exam/my-assessments/{id}/ | 学生 |
| 86 | POST | /api/exam/answer-sheets/ | 学生 |
| 87 | PUT | /api/exam/answer-sheets/{id}/answers/ | 学生 |
| 88 | POST | /api/exam/answer-sheets/{id}/submit/ | 学生 |
| 89 | GET | /api/exam/my-assessments/records/ | 学生 |
| 90 | GET | /api/exam/my-assessments/{id}/report/ | 学生 |
| 91 | GET | /api/exam/my-scores/ | 学生 |
| 92 | GET | /api/exam/my-scores/curve/ | 学生 |
| 93 | GET | /api/exam/my-growth/ | 学生 |
| 94 | POST | /api/exam/extracurricular/ | 学生 |
| 95 | GET | /api/exam/my-class/assessments/ | 学生 |
| 96 | GET | /api/exam/students/{student_id}/extracurricular/ | 教师/学校 |
| 97 | GET | /api/exam/students/{student_id}/scores/ | 教师/学校 |
| 98 | POST | /api/exam/students/{student_id}/scores/daily/ | 教师/学校 |
| 99 | GET | /api/exam/scores/template/ | 教师/学校 |
| 100 | POST | /api/exam/scores/import/ | 教师/学校 |
| 101 | POST | /api/exam/scores/supplement/ | 学校/区县/市州 |
| 102 | GET | /api/exam/students/{student_id}/scores/export/ | 教师/学校 |
| 103 | GET | /api/exam/stats/assessment/ | 学校/区县/市州/省级 |
| 104 | GET | /api/exam/stats/assessment/export/ | 学校/区县/市州/省级 |
| 105 | GET | /api/exam/stats/participation/export/ | 省级 |
| 106 | GET | /api/exam/certificates/ | 学生 |
| 107 | GET | /api/exam/certificates/{id}/ | 学生 |
| 108 | GET | /api/exam/certificates/{id}/download/ | 学生 |
| 109 | GET | /api/exam/students/{student_id}/certificates/ | 教师/学校 |
| 110 | GET | /api/exam/students/{student_id}/certificates/export/ | 教师/学校 |
| 111 | GET | /api/content/knowledge/ | 学生/题库管理员/省级 |
| 112 | POST | /api/content/knowledge/ | 题库管理员/省级 |
| 113 | GET | /api/content/knowledge/{id}/ | 学生/题库管理员/省级 |
| 114 | PUT/PATCH | /api/content/knowledge/{id}/ | 题库管理员/省级 |
| 115 | DELETE | /api/content/knowledge/{id}/ | 题库管理员/省级 |

### 6.4 测试链路建议

1. **作答链路**（student）：#1 登录 → #84 列表 → #85 详情 → #86 开始 → #87 保存 → #88 提交 → #90 报告。
2. **学生端结果**（student）：#91 我的成绩 → #92 曲线 → #93 成长曲线 → #94 上传课外学习 → #95 班级测评信息。
3. **判分评分**（teacher）：#96 查看课外学习 → #97 查看成绩 → #98 平时评分 → #99 模板 → #100 导入 → #101 补录 → #102 导出。
4. **统计**（province）：#103 统计（看 summary/by_region/by_city）→ #104 统计导出 → #105 参与率导出。
5. **证书**（student）：#106 列表 → #107 详情 → #108 下载；（teacher）→ #109 查看 → #110 导出。
6. **趣味课堂**（admin 维护 + student 只读）：#112 新增 → #111 列表 → #113 详情 → #114 修改 → #115 删除。
7. **市直属学校**（city）：#13 新增 `is_directly_affiliated=true` 学校 → #12 `directly_affiliated=1` 过滤 → #33 `directly_affiliated=1` 查市直属账号。

### 6.5 常见问题

| 现象 | 原因与解决 |
| --- | --- |
| 启动报 `no such column: ..._deleted_at` / `is_directly_affiliated` | 迁移冲突，先 `makemigrations --merge --noinput` + `migrate` |
| 登录后请求 401 | token 取 `data.access`，Header 用 `Authorization: Bearer {{access}}` |
| 注册报密码错误 | 密码需过 Django 强度校验（≥8 位、非纯数字） |
| 403 Forbidden | 角色不对，见 6.1 权限矩阵 |
| 删了资源却还查得到 | 软删除，列表默认过滤 `is_deleted=false`（账号用 `is_active`） |
| 列表结构对不上 | 列表统一 `data.list` + `data.total` + `data.page` + `data.page_size` |
| 建课程 403 | 课程写操作仅题库管理员，换 `admin` 登录 |
| 组卷后没题目 | 引用的题必须是 `approved`；或 `qtype_config` 数量超出已审核题池 |
| 下载 materials/answers/导出接口乱码 | 是文件流（zip/txt/xlsx/html），用「下载」而非「发送」测试 |
| 发布后学生看不到 | 检查 scope_type/target 是否匹配学生所在班级，且未过期、未撤回 |
| 自动组卷报「仅找到 N 道题」 | 已审核题库中该题型/难度数量不足 |
| 我的作答列表为空 | 发布范围未命中该学生班级，或不在时间窗口，或已撤回 |
| 开始作答 409 | 测评未开始/已结束，或已提交 |
| 报告报「尚未开始/未提交」 | 需先 #86 开始、#88 提交 |
| 提交后没证书 | 仅 formal 测评且得分率 ≥60% 才发证 |
| 统计为 0 | 需有学生已提交答卷；教师/学校只能看本校数据 |
| 参与率导出 403 | 仅省级管理员可用 |
| 趣味课堂学生看不到内容 | 该内容 `is_published=false`，学生只读已发布内容 |

### 6.6 限时自动提交说明（新增功能）

- 测评设置 `end_at` 后，学生若到点仍未提交，系统会**自动提交**其答卷（客观题自动判分、达标发证），避免超时未交导致漏统计、漏发证书。
- 触发方式（二选一，建议都配）：
  1. **定时任务**：Linux cron / Windows 任务计划 调用 `python manage.py auto_submit_exams`（脚本见 `scripts/auto_submit_exams.sh` / `scripts/auto_submit_exams.bat`）。
  2. **统计接口兜底**：每次调用 `#103 测评数据统计` / `#104 统计导出` 前会先执行一次自动提交。
- 验证：造一张带 `end_at`（已过期）的发布 → 学生开始作答但不提交 → 等定时任务跑一次，或直接调用 #103，再查 `#89 我的测评记录`，该答卷 `is_submitted=true`。
