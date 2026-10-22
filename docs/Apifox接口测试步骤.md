# Apifox 接口测试步骤

> 适用项目：艺术测评系统后端（Django 4.2 + DRF 3.14）。
> 本文带你从零在 Apifox 里测通接口：启动服务 → 导入接口 → 配环境 → 登录拿 token → 逐个测。

---

## 0. 准备：账号与数据

在测接口之前，先保证本地有账号和数据。项目提供了一个一键造数命令：

```bash
python manage.py seed_demo
```

执行后你会得到：

| 账号 | 密码 | 角色 | 能访问 |
|---|---|---|---|
| admin | admin123456 | 超级用户（qb_admin） | 全部接口 |
| teacher | teacher123456 | 教师 | 题库/组卷，**不能**审核、**不能**写课程/章节 |

同时造出：课程「音乐 / 美术」、若干章节、12 道已审核试题。

> 接口文档已生成在 `docs/schema.yml`（OpenAPI 3 格式），可直接导入 Apifox；浏览器打开 `/api/docs/` 也能看中文版 Swagger。

---

## 1. 启动后端服务

在 `backend` 目录打开终端：

```bash
python manage.py runserver
```

看到 `Starting development server at http://127.0.0.1:8000/` 即成功。

验证：浏览器打开 `http://127.0.0.1:8000/api/docs/`，能看到中文 Swagger 页面。

**保持该终端开着**，测接口全靠它。

---

## 2. 把接口导入 Apifox

**方式 A：上传文件（推荐）**

1. Apifox → 新建/打开一个项目
2. 左侧「导入」→ 选 **OpenAPI / Swagger**
3. 选「文件」→ 上传 `backend/docs/schema.yml`
4. 导入后左侧出现按中文分组的目录：**认证 / 用户 / 组织 / 班级 / 题库 / 试卷 / 答卷 / 证书**

**方式 B：URL 导入**

1. Apifox → 导入 → OpenAPI/Swagger → 选「URL」
2. 填 `http://127.0.0.1:8000/api/schema/`（服务器需处于启动状态）

---

## 3. 配置环境变量（服务地址）

导入后接口 URL 只有 `/api/...` 路径，需补上服务地址：

1. 左上角「环境」→ 新建环境，命名「本地」
2. 找到 **服务地址（Base URL / 前缀 URL）**，填 `http://127.0.0.1:8000`
3. 保存，并在右上角把当前环境切到「本地」

此后每个接口的完整地址自动变成 `http://127.0.0.1:8000/api/...`。

---

## 4. 登录拿 token（最关键一步）

打开「认证」分组里的 **登录** 接口（`POST /api/auth/login/`）。

**请求体**（Body → raw → JSON）：

```json
{
  "username": "admin",
  "password": "admin123456"
}
```

**响应**（注意信封结构）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "access": "eyJhbGciOiJIUzI1NiIs...",
    "refresh": "eyJhbGciOiJIUzI1NiIs..."
  }
}
```

> ⚠️ **token 在 `data.access` 里，不在顶层。** 后端把成功响应统一包成 `{code, message, data}` 信封，真实数据都在 `data` 里。

复制 `data.access` 的值，这就是登录令牌（有效期 30 分钟）。

---

## 5. 给接口配鉴权（带 token）

### 方式一：手动（先这么用）

1. 打开任意接口（如「题库」→「课程列表」）
2. 点 **Auth** 标签 → 类型选 **Bearer Token** → Token 里粘贴 access 值
3. 发送，即可正常返回数据

### 方式二：自动提取（配一次，一劳永逸）

1. 回到「登录」接口 → **后置操作** → 添加「提取变量」
   - 目标：环境变量 `token`
   - 来源：响应体，路径 `$.data.access`
   - 或用脚本：`pm.environment.set("token", pm.response.json().data.access)`
2. 项目「全局请求头」加一条：`Authorization` = `Bearer {{token}}`
3. 以后每次先跑一次登录接口，token 自动写入变量，其它接口自动带上

> 手动方式也完全够用：登录 → 复制 token → 粘到每个接口的 Auth。token 过期（30 分钟）就重新登录再粘。

---

## 6. 测试示例

配好鉴权后，按下面顺序逐个测：

**① 课程列表** — `GET /api/questionbank/courses/`
- 直接发送，应返回 `data` 里包含「音乐」「美术」两条

**② 试题列表** — `GET /api/questionbank/questions/`
- 返回 `data` 里是分页结构（`results` + `count`），共 12 道
- 可加 query 过滤：`qtype=single`、`difficulty=easy`、`status=approved`

**③ 自动组卷** — `POST /api/exam/papers/auto-generate/`

```json
{
  "subject": "music",
  "title": "音乐测试卷",
  "qtype_config": [
    { "qtype": "single", "difficulty": "easy", "count": 1 },
    { "qtype": "judge", "difficulty": "easy", "count": 1 }
  ]
}
```

- 应返回 `201`，`data` 是一张草稿试卷 + 抽中的题目；记下返回的试卷 `id`

**④ 下载试卷材料** — `GET /api/exam/papers/{id}/materials/`
- 把 `{id}` 换成上一步的试卷 id，发送后应下载到一个 zip

**⑤ 发布试卷** — `POST /api/exam/publishes/`

```json
{
  "paper": 1,
  "scope_type": "grade"
}
```

- 说明：`scope_type=grade` 不需要 target；若用 `scope_type=school`，接口会校验要求 `target_school` 必填（当前没建学校，会报校验错——这说明校验生效了）

---

## 7. 常见问题排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `401` | 没带 token，或 token 过期（30 分钟） | 重新登录复制新 token；或调 `/api/auth/refresh/` 刷新 |
| `403` | 角色权限不够 | 换 `admin`；`teacher` 不能审核、不能写课程/章节 |
| `404` | 路径/资源不存在 | 检查 id 是否正确、URL 拼写 |
| 返回空列表 | 过滤条件太严 | 去掉 query 过滤条件再试 |
| 字段名是英文 | 正常 | JSON 的 key 必须是英文，字段中文说明在接口文档里能看到 |

---

## 8. 两个重要约定

1. **所有 2xx 响应都带信封** `{code, message, data}`，真正要的数据在 `data` 里——看返回时别找错层级。
2. 现在测的是「接口通不通、参数校验对不对」；等前端写完，两边再用这份文档对齐字段。
