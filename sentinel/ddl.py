"""第 3 步：从任务文本里猜出截止时间，并排出紧急程度。

只用规则，不用 AI：
    1. 先找"绝对日期"：10月20日、2026-10-20
    2. 再找"相对日期"：今天 / 明天 / 本周五 / 下周日 / 月底前 / N天后
    3. 再找"时间点"：23:59、晚上12点，找不到就默认 23:59
    4. 都找不到就把截止时间记为 None（未知），报告里单独标出来
    5. 把同主题、被"以……为准"更正过的旧任务标成"已作废"

升级点：
    * parse_due_detail 额外返回 explicit（原文是否明确写了日期）与 ambiguous（是否含糊），
      让上层能区分"原文明确表达"与"程序推断"。
    * 时区说明：本程序把消息时间与"现在"都当作本机本地时间处理，
      不解析时区后缀（如 +08:00 / UTC），也不做夏令时换算。
"""

import re
from datetime import datetime, timedelta

# 星期几 -> 0 表示周一，6 表示周日
WEEKDAYS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

_ABS_FULL = re.compile(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})")
_ABS_MD = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]")
_WEEKDAY = re.compile(r"(本|这|下)?\s*(周|星期|礼拜)\s*([一二三四五六日天])")
_AFTER_DAYS = re.compile(r"(\d+)\s*天\s*(后|以后|之内|内)")
_CLOCK_COLON = re.compile(r"(\d{1,2})\s*[:：]\s*(\d{2})")
_CLOCK_CN = re.compile(r"(上午|早上|中午|下午|晚上|凌晨)?\s*(\d{1,2})\s*[点时]")


def _fix_hour(hour: int, minute: int, period: str):
    """把 12 小时制换成 24 小时制，比如"下午3点"-> 15 点。"""
    if period in ("下午", "晚上") and hour < 12:
        hour += 12
    if period in ("晚上", "夜里") and hour == 12:
        return 23, 59
    if hour > 23:
        hour = 23
    return hour, minute


def _parse_clock(text: str):
    """从文本里找时间点，返回 (时, 分)；找不到返回 None。"""
    m = _CLOCK_COLON.search(text)
    if m:
        return _fix_hour(int(m.group(1)), int(m.group(2)), "")
    m = _CLOCK_CN.search(text)
    if m:
        return _fix_hour(int(m.group(2)), 0, m.group(1) or "")
    return None


def _last_day_of_month(ref_time: datetime):
    """当月最后一天。"""
    if ref_time.month == 12:
        return datetime(ref_time.year, 12, 31).date()
    first_of_next = datetime(ref_time.year, ref_time.month + 1, 1).date()
    return first_of_next - timedelta(days=1)


def parse_due_detail(text: str, ref_time: datetime):
    """猜这条消息的截止时间（详细版）。

    返回 dict：
        due         : datetime 或 None
        due_source  : 推测依据（写给用户看）
        explicit    : True 表示原文明确写了日期；False 表示程序推断
        ambiguous   : True 表示表达含糊 / 只给了"最近一次"这类猜测
        time_explicit : 原文是否明确写了时间点
    """
    date = None
    source = None
    explicit = False
    ambiguous = False
    time_explicit = False

    # 1. 绝对日期：2026-10-20 或 10月20日
    m = _ABS_FULL.search(text)
    if m:
        date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        source = "绝对日期"
        explicit = True
    if date is None:
        m = _ABS_MD.search(text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            year = ref_time.year
            if datetime(year, month, day).date() < ref_time.date():
                year += 1
            date = datetime(year, month, day).date()
            source = "绝对日期（按最近一次推测）"
            explicit = True
            ambiguous = True  # 没写年份，只能猜最近一次

    # 2. 相对日期：今天 / 明天 / N天后
    if date is None:
        if "今天" in text:
            date, source = ref_time.date(), "相对日期（今天）"
        elif "大后天" in text:
            date, source = ref_time.date() + timedelta(days=3), "相对日期（大后天）"
        elif "后天" in text:
            date, source = ref_time.date() + timedelta(days=2), "相对日期（后天）"
        elif "明天" in text:
            date, source = ref_time.date() + timedelta(days=1), "相对日期（明天）"
        else:
            m = _AFTER_DAYS.search(text)
            if m:
                date = ref_time.date() + timedelta(days=int(m.group(1)))
                source = "相对日期（N天后）"

    # 3. 本周五 / 下周日 这类
    if date is None:
        m = _WEEKDAY.search(text)
        if m:
            prefix = m.group(1) or ""
            target = WEEKDAYS[m.group(3)]
            ahead = target - ref_time.weekday()
            if prefix == "下":
                ahead += 7
            elif ahead < 0:
                ahead += 7
            date = ref_time.date() + timedelta(days=ahead)
            source = "相对日期（周几）"

    # 4. 月底前 / 月末
    if date is None and ("月底" in text or "月末" in text):
        date, source = _last_day_of_month(ref_time), "相对日期（月底）"

    if date is None:
        return {
            "due": None, "due_source": "无法识别",
            "explicit": False, "ambiguous": True, "time_explicit": False,
        }

    clock = _parse_clock(text)
    if clock is None:
        hour, minute = 23, 59
    else:
        hour, minute = clock
        time_explicit = True

    due = datetime(date.year, date.month, date.day, hour, minute)
    return {
        "due": due, "due_source": source,
        "explicit": explicit, "ambiguous": ambiguous, "time_explicit": time_explicit,
    }


def parse_due(text: str, ref_time: datetime):
    """猜截止时间（兼容旧接口）。

    返回 (due, due_source)。
    """
    d = parse_due_detail(text, ref_time)
    return d["due"], d["due_source"]


def status_of(due, now: datetime) -> str:
    """根据"离现在还有多久"给出紧急程度。"""
    if due is None:
        return "未知"
    if due < now:
        return "已过期"
    left = due - now
    if left <= timedelta(days=1):
        return "紧急"
    if left <= timedelta(days=3):
        return "即将"
    return "一般"


def remaining_text(due, now: datetime) -> str:
    """把剩余时间写成人话，比如"还剩 2 天 3 小时" / "已过期 5 小时"。"""
    if due is None:
        return "未知"
    delta = due - now
    overdue = delta.total_seconds() < 0
    secs = abs(int(delta.total_seconds()))
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days} 天")
    if hours:
        parts.append(f"{hours} 小时")
    if not days and minutes:
        parts.append(f"{minutes} 分钟")
    if not parts:
        parts.append("不到 1 分钟")
    return ("已过期 " if overdue else "还剩 ") + " ".join(parts)