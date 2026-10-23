# A 模块（基础底座 · 账号组织）Apifox 接口测试文档

> 适用对象：验收成员 A 交付的基础底座接口（认证、用户、行政区、学校、班级、账号管理、操作日志）。
> 本文档所有接口统一按同一模板编写：每个接口含 **接口编号、接口名称、请求方法、请求路径、请求头、权限角色、请求体 JSON、请求字段表、响应示例 JSON、响应字段表**。

---

## 1. 文档说明

### 1.1 接口清单

A 模块共 **42 个接口**，按资源分 8 组：

| 分组 | 接口编号 | 数量 | 说明 |
| --- | --- | --- | --- |
| 认证 | #1 - #2 | 2 | 登录、刷新令牌 |
| 用户 | #3 - #6 | 4 | 注册、当前用户查询/修改、修改密码 |
| 组织（行政区） | #7 - #11 | 5 | Region CRUD |
| 组织（学校） | #12 - #16 | 5 | School CRUD |
| 班级 | #17 - #28 | 12 | 班级 CRUD + 学生/教师业务操作 |
| 班级关系（只读） | #29 - #32 | 4 | 班级学生 / 班级教师列表与详情 |
| 账号管理 | #33 - #41 | 9 | 统一账号 CRUD + 批量/重置/材料 |
| 操作日志 | #42 | 1 | 系统日志查询 |

> A 模块是「数据底座」，B 的题库/试卷、C 的作答/证书都依赖 A 造出的账号、行政区、学校、班级。建议先测 A，再测 B/C。

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

分页查询参数：`?page=1`（页码）、`?page_size=20`（每页条数，最大 100）。

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
| null | 空值 | `null` |

---

## 3. 前置准备

### 3.1 迁移与演示数据

```bash
python manage.py makemigrations --merge --noinput
python manage.py migrate
python manage.py seed_demo
```

`seed_demo` 幂等，造好：行政区三级（四川省→成都市→锦江区）、学校（测试小学）、班级（三年级一班）、学生入班，以及 7 个角色账号、4 道已审核试题、1 张已发布试卷。

### 3.2 启动服务

```bash
python manage.py runserver 8000
```

### 3.3 测试账号

| 账号 | 密码 | 角色 | 适合测试的接口 |
| --- | --- | --- | --- |
| student | student123456 | 学生 | 班级 join/quit/change、班级详情 |
| teacher | teacher123456 | 教师 | 班级 CRUD、审核、账号 materials |
| school | school123456 | 学校管理员 | 班级、账号管理、region/school 查看 |
| district | district123456 | 区县管理员 | school CRUD、账号管理 |
| city | city123456 | 市州管理员 | region 写、school CRUD、账号 |
| province | province123456 | 省级管理员 | region 全部、日志、账号 |
| admin | admin123456 | 题库管理员(超管) | 日志、兜底排查 |

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

> 以上为当前开发库实际值，不确定时以接口返回为准（如 `GET /api/org/regions/`）。

---

## 4. Apifox 配置

### 4.1 导入接口

1. Apifox →「导入数据」→「OpenAPI / Swagger」→ 选择 `docs/schema.yml`。
2. 自动生成分组：认证 / 用户 / 组织 / 班级 / 账号 / 日志 / 题库 / 试卷 / 答卷 / 证书。

> 不同步时重新生成：`python manage.py spectacular --file docs/schema.yml`；或浏览器打开 `http://127.0.0.1:8000/api/docs/`。

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
2. 在后置操作添加「提取变量」：表达式 `$.data.access` → 写入变量 `access`。

> 换角色 = 换账号重新登录 = 重新提取 token。建议建多个环境分别缓存各角色 token。

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
  "username": "province",
  "password": "province123456"
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

### 5.3 组织 - 行政区（Region）

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

### 5.4 组织 - 学校（School）

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
  "phone": "028-88888888"
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

## 6. 附录

### 6.1 角色权限矩阵

| 接口 | 允许角色 |
| --- | --- |
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

### 6.2 枚举值

| 字段 | 取值 |
| --- | --- |
| 角色 role | student / teacher / school / district / city / province / qb_admin |
| 行政区 level | province / city / district |
| 班级关系 status | pending / approved / rejected |

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

### 6.4 常见问题

| 现象 | 原因与解决 |
| --- | --- |
| 启动报 `no such column: ..._deleted_at` | 迁移冲突，先 `makemigrations --merge --noinput` + `migrate` |
| 登录后请求 401 | token 取 `data.access`，Header 用 `Authorization: Bearer {{access}}` |
| 注册报密码错误 | 密码需过 Django 强度校验（≥8 位、非纯数字） |
| 403 Forbidden | 角色不对，见 6.1 权限矩阵 |
| 删了资源却还查得到 | 软删除，列表默认过滤 `is_deleted=false` |
| 列表结构对不上 | 列表统一 `data.list` + `data.total` + `data.page` + `data.page_size` |
