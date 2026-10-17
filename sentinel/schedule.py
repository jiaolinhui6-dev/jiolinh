"""把任务编排成"结构化时间表"：按周（周一到周日）分组展示。

题目要求输出两块：
    1. 结构化时间表 —— 本模块负责：把任务按截止日期落到"本周 / 下周 / 更远 / 已过期 / 时间未知"，
       并按周内星期排列，形成看得见的时间轴。
    2. 按紧急度排序的本周待办 —— 由 tasks.sort_tasks + status 提供（沿用现有逻辑）。

只做"编排 + 归组"，不修改任何任务字段，也不产生新的日期推断。
"""

from datetime import datetime, timedelta

# 周一~周日
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

BUCKET_ORDER = ["已过期", "今天", "明天", "本周", "下周", "更远", "时间未知"]


def _day_start(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _week_start(day: datetime) -> datetime:
    """返回所在周的周一 00:00。"""
    return _day_start(day) - timedelta(days=day.weekday())


def _bucket_of(due: datetime, now: datetime) -> str:
    """判断一个截止时间属于哪个分区。"""
    d = _day_start(due)
    today = _day_start(now)
    if d < today:
        return "已过期"
    if d == today:
        return "今天"
    if d == today + timedelta(days=1):
        return "明天"
    this_week = _week_start(today)
    if d < this_week + timedelta(days=7):
        return "本周"
    if d < this_week + timedelta(days=14):
        return "下周"
    return "更远"


def build_schedule(tasks: list, now: datetime | None = None) -> dict:
    """把任务编排成结构化时间表。

    参数：
        tasks : 任务 dict 列表（需含 due / status / superseded / excluded 等字段）
        now   : 参考时间

    返回：
        {
          "now": "YYYY-MM-DD HH:MM",
          "week_start": "YYYY-MM-DD",
          "week_end": "YYYY-MM-DD",
          "days": [ {date, weekday, label, is_today, is_weekend, items:[...]}, ... ],  # 本周七天
          "buckets": [ {key, label, count, items:[...]}, ... ],   # 已过期/今天/本周/下周/更远/时间未知
          "week_total": 本周(含今天/明天)待办数,
          "unscheduled": 时间未知数量,
        }
    说明：items 里的每项是原始 task dict 的浅拷贝（不改动原对象）。
    """
    if now is None:
        now = datetime.now()

    this_week = _week_start(now)
    # 本周七天骨架（周一到周日）
    days = []
    for i in range(7):
        day = this_week + timedelta(days=i)
        days.append({
            "date": day.strftime("%Y-%m-%d"),
            "weekday": WEEKDAY_NAMES[i],
            "label": day.strftime("%m-%d") + " " + WEEKDAY_NAMES[i],
            "is_today": _day_start(day) == _day_start(now),
            "is_weekend": i >= 5,
            "items": [],
        })

    buckets = {k: [] for k in BUCKET_ORDER}

    for t in tasks:
        if t.get("superseded") or t.get("excluded"):
            continue
        item = dict(t)
        due = t.get("due")
        if due is None:
            buckets["时间未知"].append(item)
            continue
        bucket = _bucket_of(due, now)
        buckets[bucket].append(item)
        # 周格子按"截止日期是否落在本周（周一~周日）"来放，
        # 这样本周内已经过期的任务（如周三的作业）也能出现在周三那一列。
        due_day = _day_start(due)
        if this_week <= due_day < this_week + timedelta(days=7):
            day_idx = (due_day - this_week).days
            if 0 <= day_idx < 7:
                days[day_idx]["items"].append(item)

    # 每一天内部按时间排序
    for d in days:
        d["items"].sort(key=lambda x: x.get("due") or datetime.max)

    out_buckets = []
    for k in BUCKET_ORDER:
        items = buckets[k]
        items.sort(key=lambda x: x.get("due") or datetime.max)
        out_buckets.append({"key": k, "label": k, "count": len(items), "items": items})

    week_total = sum(len(d["items"]) for d in days)

    return {
        "now": now.strftime("%Y-%m-%d %H:%M"),
        "week_start": (this_week).strftime("%Y-%m-%d"),
        "week_end": (this_week + timedelta(days=6)).strftime("%Y-%m-%d"),
        "days": days,
        "buckets": out_buckets,
        "week_total": week_total,
        "unscheduled": len(buckets["时间未知"]),
    }
