"""通用 Excel 导出工具。

用法（在 ViewSet 的 action 中）::

    from apps.common.export import export_excel

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self.filter_queryset(self.get_queryset())
        fields = [
            ("username", "账号"),
            ("real_name", "姓名"),
            ("role", "角色"),
        ]
        return export_excel(qs, fields, filename="用户列表.xlsx")

``fields`` 元素是 ``(字段名/字典key, 表头)`` 二元组。
``data`` 支持 QuerySet、list[dict]、list[Model]。
"""
import io
import re
from typing import Iterable, Sequence, Tuple, Union

from django.http import HttpResponse
from openpyxl import Workbook

DataRow = Union[dict, object]
FieldSpec = Tuple[str, str]

# Excel 工作表名非法字符
_INVALID_SHEET_CHARS = re.compile(r'[:\\/?*\[\]]')


def _get_value(row: DataRow, field: str):
    """从一行数据（dict 或 Model 实例）中按 field 取值。"""
    if isinstance(row, dict):
        return row.get(field)
    # Model 实例
    value = getattr(row, field, None)
    # 支持 callable（如 get_role_display）
    if callable(value):
        try:
            return value()
        except TypeError:
            return value
    return value


def _display_width(text) -> int:
    """计算显示宽度（中文/全角按 2，其余按 1）。"""
    s = str(text) if text is not None else ""
    return sum(2 if ord(c) > 127 else 1 for c in s)


def _safe_sheet_name(name: str) -> str:
    """工作表名去非法字符并截断至 31 字符。"""
    name = _INVALID_SHEET_CHARS.sub("", name or "Sheet1")
    return name[:31] or "Sheet1"


def export_excel(
    data: Iterable[DataRow],
    fields: Sequence[FieldSpec],
    filename: str = "export.xlsx",
    sheet_name: str = "Sheet1",
) -> HttpResponse:
    """将数据导出为 Excel 文件响应。

    :param data: QuerySet 或 list[dict] 或 list[Model]
    :param fields: [(字段名, 表头), ...]
    :param filename: 下载文件名
    :param sheet_name: 工作表名（自动去除非法字符并截断至 31 字符）
    :return: HttpResponse（Excel 二进制流）
    """
    wb = Workbook()
    ws = wb.active
    ws.title = _safe_sheet_name(sheet_name)

    # 表头
    headers = [label for _, label in fields]
    ws.append(headers)

    # 数据行 + 计算各列最大宽度
    col_widths = [_display_width(h) for h in headers]
    for row in data:
        values = [_get_value(row, field) for field, _ in fields]
        ws.append(values)
        for i, v in enumerate(values):
            col_widths[i] = max(col_widths[i], _display_width(v))

    # 应用列宽
    for idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = min(
            max(width + 2, 12), 60
        )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    from urllib.parse import quote
    encoded_filename = quote(filename)

    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    # 同时提供 ASCII filename 回退和 RFC 5987 filename*，兼容旧客户端
    response["Content-Disposition"] = (
        f'attachment; filename="export.xlsx"; filename*=UTF-8\'\'{encoded_filename}'
    )
    return response
