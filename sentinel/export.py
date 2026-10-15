"""把任务列表导出成 CSV / JSON / XLSX（网页下载按钮与命令行共用）。

健壮性说明：
    * 任务是 dict，msg_time / due 可能是 datetime（命令行内部对象），
      也可能是前端回传的字符串。本模块对两种形式都兼容。
    * 只导出任务本身的结构化字段，不包含 API Key、不包含环境变量。

编码说明（重要）：
    * CSV 统一带 UTF-8 BOM（utf-8-sig），Excel 双击打开不乱码。
      to_csv() 返回带 BOM 的文本；to_csv_bytes() 返回带 BOM 的字节，供 HTTP 下载。
    * XLSX 由 openpyxl 生成，返回字节流；中文、列宽、冻结首行、筛选均已设置。
      openpyxl 是可选依赖：未安装时 to_xlsx 抛 ExportUnavailable，网页会提示改用 CSV。
"""

import csv
import io
import json
from datetime import datetime

# CSV 列顺序（CSV / XLSX 共用，保证两边字段一致）
FIELDS = ["任务", "课程群", "发送人", "截止时间", "剩余时间", "状态",
          "截止依据", "原文明确", "建议确认", "来源", "消息时间", "原始消息"]

# 各列建议宽度（中文字符大约占 2 个宽度单位）
COLUMN_WIDTHS = {
    "任务": 22, "课程群": 18, "发送人": 12, "截止时间": 18, "剩余时间": 16,
    "状态": 10, "截止依据": 26, "原文明确": 10, "建议确认": 10,
    "来源": 8, "消息时间": 18, "原始消息": 52,
}

# UTF-8 BOM，确保 Excel 正确识别中文编码
BOM = "\ufeff"

try:  # openpyxl 为可选依赖
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:  # pragma: no cover - 视环境而定
    HAS_OPENPYXL = False


class ExportUnavailable(Exception):
    """导出所需能力不可用（例如没有安装 openpyxl）。"""


def _fmt(value, fmt="%Y-%m-%d %H:%M") -> str:
    """把 datetime 或字符串统一格式化成字符串。"""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return str(value)


def _fmt_time(value) -> str:
    """消息时间：datetime -> 'YYYY-MM-DD HH:MM'；字符串原样返回。"""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value) if value else ""


def _row(task: dict) -> dict:
    return {
        "任务": task.get("topic") or (task.get("text") or "")[:20],
        "课程群": task.get("chat", ""),
        "发送人": task.get("sender", ""),
        "截止时间": _fmt(task.get("due")) or "未知",
        "剩余时间": task.get("remaining", ""),
        "状态": task.get("status", ""),
        "截止依据": task.get("due_source", ""),
        "原文明确": "是" if task.get("explicit") else "否",
        "建议确认": "是" if task.get("needs_confirm") else "否",
        "来源": task.get("origin", "rule"),
        "消息时间": _fmt_time(task.get("msg_time")),
        "原始消息": task.get("text", ""),
    }


def to_csv(tasks: list) -> str:
    """生成带 UTF-8 BOM 的 CSV 文本（Excel 直接双击不乱码）。"""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS)
    writer.writeheader()
    for t in tasks:
        writer.writerow(_row(t))
    return BOM + buf.getvalue()


def to_csv_bytes(tasks: list) -> bytes:
    """生成带 UTF-8 BOM 的 CSV 字节流，供 HTTP 直接下载。"""
    return to_csv(tasks).encode("utf-8")


def to_json(tasks: list, *, indent: int | None = 2) -> str:
    """生成 JSON 文本（可追溯所需字段齐全，但不含任何密钥）。"""
    payload = []
    for t in tasks:
        payload.append({
            "id": t.get("id"),
            "topic": t.get("topic"),
            "chat": t.get("chat"),
            "sender": t.get("sender"),
            "due": _fmt(t.get("due")) or None,
            "due_source": t.get("due_source"),
            "explicit": bool(t.get("explicit")),
            "ambiguous": bool(t.get("ambiguous")),
            "remaining": t.get("remaining"),
            "status": t.get("status"),
            "superseded": bool(t.get("superseded")),
            "excluded": bool(t.get("excluded")),
            "needs_confirm": bool(t.get("needs_confirm")),
            "confidence": t.get("confidence"),
            "origin": t.get("origin", "rule"),
            "msg_time": _fmt_time(t.get("msg_time")) or None,
            "raw_message": t.get("text"),
        })
    return json.dumps(payload, ensure_ascii=False, indent=indent)


def to_xlsx(tasks: list) -> bytes:
    """用 openpyxl 生成 XLSX 字节流。

    特性：表头加粗着色、首行冻结、自动筛选、按内容设置列宽、长文本自动换行。
    """
    if not HAS_OPENPYXL:
        raise ExportUnavailable("未安装 openpyxl，无法导出 XLSX。请运行：pip install openpyxl")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "待办清单"

    # 表头
    ws.append(FIELDS)
    header_fill = PatternFill("solid", fgColor="2563EB")
    header_font = Font(bold=True, color="FFFFFF")
    for col_idx, _name in enumerate(FIELDS, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 数据行
    for t in tasks:
        row = _row(t)
        ws.append([row[name] for name in FIELDS])

    # 列宽 + 长文本换行
    for col_idx, name in enumerate(FIELDS, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = COLUMN_WIDTHS.get(name, 16)
        if name in ("原始消息", "截止依据"):
            for r in range(2, ws.max_row + 1):
                ws.cell(row=r, column=col_idx).alignment = Alignment(wrap_text=True, vertical="top")

    # 冻结首行 + 自动筛选
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(FIELDS))}{max(ws.max_row, 1)}"

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def to_xlsx_stream(tasks: list):
    """返回可直接读取的字节流（BytesIO），方便测试与 HTTP 下载。"""
    return io.BytesIO(to_xlsx(tasks))