"""OpenAPI 后处理：为 Apifox 导入生成中文分组与中文接口名。

drf-spectacular 生成的 operationId / tags 默认是英文，Apifox 导入时直接
用它当接口名和分组名。此 hook 在生成 schema 后统一替换为中文，避免逐视图
加注解。
"""
# (路径前缀, 中文分组, 资源名, 是否标准 CRUD 路由, 是否用 docstring 派生接口名)
ROUTES = [
    ("/api/auth/login/", "认证", "登录", False, False),
    ("/api/auth/refresh/", "认证", "刷新令牌", False, False),
    ("/api/users/register/", "用户", "注册", False, True),
    ("/api/users/me/", "用户", "当前用户", False, True),
    ("/api/users/change-password/", "用户", "修改密码", False, True),
    ("/api/org/regions/", "组织", "地区", True, True),
    ("/api/org/schools/", "组织", "学校", True, True),
    ("/api/classroom/classes/", "班级", "班级", True, True),
    ("/api/classroom/class-teachers/", "班级", "班级教师", True, True),
    ("/api/classroom/class-students/", "班级", "班级学生", True, True),
    ("/api/questionbank/courses/", "题库", "课程", True, True),
    ("/api/questionbank/chapters/", "题库", "章节", True, True),
    ("/api/questionbank/questions/", "题库", "试题", True, True),
    ("/api/exam/papers/", "试卷", "试卷", True, True),
    ("/api/exam/paper-questions/", "试卷", "试卷试题", True, True),
    ("/api/exam/publishes/", "试卷", "发布", True, True),
    ("/api/exam/answer-sheets/", "答卷", "答卷", True, True),
    ("/api/exam/answers/", "答卷", "答题明细", True, True),
    ("/api/exam/certificates/", "证书", "证书", True, True),
]

_CRUD_VERBS = ("get", "post", "put", "patch", "delete")

# 标准 CRUD 动作 -> 中文接口名（lambda 用于控制“新增/更新/删除”前置、其余后置）
_CRUD_NAME = {
    "list": lambda resource: f"{resource}列表",
    "create": lambda resource: f"新增{resource}",
    "retrieve": lambda resource: f"{resource}详情",
    "update": lambda resource: f"更新{resource}",
    "partial_update": lambda resource: f"更新{resource}",
    "destroy": lambda resource: f"删除{resource}",
}

# 详情路由（前缀 + {id}/）上各 HTTP 方法对应的 CRUD 动作
_DETAIL_VERBS = {
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy",
}


def _title(description):
    """取 docstring 首行作为简短中文标题（去掉冒号后说明与句末标点）。"""
    if not description:
        return ""
    line = description.strip().splitlines()[0].strip()
    for sep in ("：", ":"):
        if sep in line:
            line = line.split(sep)[0].strip()
            break
    return line.rstrip("。.!！；;")


def chinese_postprocess(result, generator, request, public):
    """把所有 operation 的 tags 换成中文分组、summary 换成中文接口名。"""
    paths = result.get("paths") or {}
    for path, ops in paths.items():
        matched = None
        for route in ROUTES:
            if path.startswith(route[0]):
                matched = route
                break
        if matched is None:
            continue
        prefix, tag, resource, is_crud, use_desc = matched

        for method, op in ops.items():
            if method not in _CRUD_VERBS:
                continue
            op["tags"] = [tag]

            verb = None
            if is_crud:
                if path == prefix:
                    verb = "list" if method == "get" else ("create" if method == "post" else None)
                elif path == prefix + "{id}/":
                    verb = _DETAIL_VERBS.get(method)

            if verb:
                op["summary"] = _CRUD_NAME[verb](resource)
            elif use_desc:
                op["summary"] = _title(op.get("description")) or resource
            else:
                op["summary"] = resource

    return result
