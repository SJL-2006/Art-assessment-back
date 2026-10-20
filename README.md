# 艺术素质测评系统 · 后端

基于 **Django 4.2 + Django REST Framework + SimpleJWT** 的 RESTful 后端骨架。

## 技术栈

| 组件 | 版本 | 用途 |
| --- | --- | --- |
| Django | 4.2 LTS | Web 框架 |
| djangorestframework | 3.14 | REST API |
| djangorestframework-simplejwt | 5.3 | JWT 认证 |
| django-cors-headers | 4.3 | 跨域 |
| SQLite（默认）/ MySQL（生产） | - | 数据库 |

## 快速开始

```bash
cd backend
pip install -r requirements.txt

# 生成数据库迁移并建库
python manage.py makemigrations
python manage.py migrate

# 创建超级管理员（可登录 /admin/）
python manage.py createsuperuser

# 启动开发服务器
python manage.py runserver
```

## 目录结构

```
backend/
├── manage.py
├── config/                 # 项目配置
│   ├── settings/
│   │   ├── base.py         # 公共配置（DRF/JWT/CORS/中间件）
│   │   ├── dev.py          # 开发（SQLite）
│   │   └── prod.py         # 生产（MySQL）
│   └── urls.py             # 根路由
└── apps/
    ├── common/             # 统一响应/分页/异常/角色权限/操作日志
    ├── org/                # 行政区(Region)、学校(School)
    ├── users/              # 自定义 User + 角色 + 注册/登录/改密
    ├── classroom/          # 班级、班级学生/教师关系
    ├── questionbank/       # 课程、章节、试题、试题资源、试题审核
    └── exam/               # 试卷、发布、答卷、成绩、证书
```

## 角色体系（`User.role`）

`student` 学生 · `teacher` 教师 · `school` 学校管理员 · `district` 区县管理员 ·
`city` 市州管理员 · `province` 省级管理员 · `qb_admin` 题库管理员

角色权限用 `apps/common/permissions.py` 的 `has_role(*roles)` 工厂控制，例如：

```python
permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_QB_ADMIN)]
```

## 接口约定

### 统一响应信封

所有接口返回：

```json
{ "code": 0, "message": "ok", "data": { } }
```

- `code = 0` 成功；`400` 参数错误、`401` 未认证、`403` 无权限、`404` 不存在、`500` 服务端错误。
- 列表接口的 `data` 为 `{ "list": [], "total": 0, "page": 1, "page_size": 20 }`。

### 认证

登录获取 JWT，后续请求携带 `Authorization: Bearer <access_token>`。

```bash
# 登录
POST /api/auth/login/     { "username": "...", "password": "..." }
# 刷新
POST /api/auth/refresh/   { "refresh": "..." }
```

### 主要路由前缀

| 前缀 | 模块 |
| --- | --- |
| `/api/auth/` | 登录 / 刷新令牌 |
| `/api/users/` | 注册、当前用户、修改密码 |
| `/api/org/` | 行政区、学校 |
| `/api/classroom/` | 班级、班级师生关系 |
| `/api/questionbank/` | 课程、章节、试题、试题资源、审核 |
| `/api/exam/` | 试卷、发布、答卷、答题、证书 |

## 分层约定

- `models.py` 只放数据模型与枚举常量；
- `serializers.py` 做字段校验与序列化；
- `views.py` 用 `BaseViewSet`（统一删除语义）暴露 CRUD，业务规则放视图或独立 service；
- 业务错误抛 `apps.common.exceptions.ApiException`；
- 数据库变更统一通过 `makemigrations` 生成迁移，禁止手改已应用的迁移。

## 说明

- 当前为**框架骨架**：模型/接口已按功能设计铺好，复杂的业务流程（自动组卷、客观题自动判分、成绩统计报表、证书生成、多级账号数据隔离等）需在后续迭代补充到对应 `views.py`/`service`。
- 生产部署：设置 `DJANGO_SETTINGS_MODULE=config.settings.prod`，配置 `.env` 中的 MySQL 与域名白名单。
