"""多级数据隔离：`filter_by_scope()` 让同一套 ViewSet 按调用者角色自动收敛数据范围。

设计依据：《开发任务分工》约定"一套实现 + 作用域参数"覆盖 5 级账号查询，避免 B/C 各自写 5 遍。
A 交付给 B/C 的核心地基——B/C 的统计口径依赖此方法统一。
"""
from typing import Optional

from django.db.models import QuerySet

from apps.users.models import User


def _get_descendant_region_ids(region) -> list:
    """递归拿到某行政区自身 + 所有子孙的 ID 列表（支持省→市→区三级）。"""
    if region is None:
        return []
    ids = [region.id]
    children = region.children.all()
    for child in children:
        ids.extend(_get_descendant_region_ids(child))
    return ids


def filter_by_scope(
    qs: QuerySet,
    user: User,
    *,
    region_field: str = "region",
    school_field: str = "school",
    teacher_field: Optional[str] = None,
) -> QuerySet:
    """按用户角色自动收敛查询集范围。

    参数：
        qs:        待过滤的 QuerySet
        user:      当前请求用户
        region_field: 模型关联 Region 的字段名（默认 "region"），可为 None 表示此模型不关联行政区
        school_field: 模型关联 School 的字段名（默认 "school"），可为 None 表示不关联学校
        teacher_field: 模型关联教师的字段名，仅当业务需要按教师隔离时传入

    返回：过滤后的 QuerySet（角色无权限时返回空 queryset）

    角色 → 范围映射：
        province / qb_admin → 全部
        city                → 本市 + 下属区县 + 市属学校
        district            → 本区县 + 本区县下属学校
        school              → 本校
        teacher             → 所教班级（需业务侧进一步 join 班级关系，此处保留 school 兜底）
        student             → 空（学生不做列表查询，由各接口自行按"仅本人"处理）
    """
    if user.is_superuser:
        return qs

    role = getattr(user, "role", None)

    # 1. 不限范围的角色
    if role in (User.ROLE_PROVINCE, User.ROLE_QB_ADMIN):
        return qs

    # 2. 市州 → 本市 + 下属所有区县 + 市属学校
    if role == User.ROLE_CITY:
        if user.region_id is None:
            return qs.none()
        region_ids = _get_descendant_region_ids(user.region)
        # 有 region_field 的模型
        if region_field and hasattr(qs.model, region_field):
            qs = qs.filter(**{f"{region_field}__id__in": region_ids})
        # 有 school_field 的模型 → 按学校所属区域过滤
        if school_field and hasattr(qs.model, school_field):
            qs = qs.filter(**{f"{school_field}__region_id__in": region_ids})
        return qs

    # 3. 区县 → 本区县 + 本区县下属学校
    if role == User.ROLE_DISTRICT:
        if user.region_id is None:
            return qs.none()
        region_ids = _get_descendant_region_ids(user.region)
        if region_field and hasattr(qs.model, region_field):
            qs = qs.filter(**{f"{region_field}__id__in": region_ids})
        if school_field and hasattr(qs.model, school_field):
            qs = qs.filter(**{f"{school_field}__region_id__in": region_ids})
        return qs

    # 4. 学校管理员 → 本校
    if role == User.ROLE_SCHOOL:
        if user.school_id is None:
            return qs.none()
        if school_field and hasattr(qs.model, school_field):
            return qs.filter(**{school_field: user.school})
        # 没有 school 关联时回退到 region
        if region_field and hasattr(qs.model, region_field):
            return qs.filter(**{region_field: user.region})
        return qs

    # 5. 教师 → 所教班级相关（此处按 school 兜底，具体班级隔离由业务接口自行处理）
    if role == User.ROLE_TEACHER:
        if teacher_field and hasattr(qs.model, teacher_field):
            return qs.filter(**{teacher_field: user})
        if school_field and hasattr(qs.model, school_field):
            return qs.filter(**{school_field: user.school})
        return qs

    # 6. 学生 → 空（列表查询不返回数据，学生的数据由各接口按"仅本人"过滤）
    if role == User.ROLE_STUDENT:
        return qs.none()

    # 未知角色 → 默认空
    return qs.none()
