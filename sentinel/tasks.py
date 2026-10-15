"""组装最终任务对象：规则解析 + 去重 / 更正 / 可信度。

一条任务（dict）包含：
    id            : 稳定 ID（由群名 + 主题 + 截止时间 + 原文派生，便于前端引用/去重）
    msg_time/sender/chat/text : 原始消息（始终保留，AI 不得覆盖）
    matched       : 命中的关键词
    topic/topics  : 主题（第一个 / 全部），比如"实验一"
    due/due_source: 截止时间与依据
    explicit      : 截止日期是否为原文明确表达
    ambiguous     : 是否含糊（需要确认）
    time_explicit : 原文是否明确写了时间点
    status        : 已过期 / 紧急 / 即将 / 一般 / 未知 / 待确认 / 已作废
    superseded    : 是否被"以……为准"的更正消息作废
    superseded_by : 作废它的那条第 index（便于溯源）
    confidence    : 规则置信度
    needs_confirm : 是否建议人工确认
    origin        : rule / ai / user（结果来源，前端据此区分）
    index         : 在原始消息中的序号
"""

import hashlib
from datetime import datetime

from sentinel.extract import extract_candidates, is_correction
from sentinel.ddl import parse_due_detail, status_of, remaining_text


def _make_id(task: dict) -> str:
    """生成稳定 ID：同一群 + 同一主题 + 同一截止时间 + 原文前 40 字。"""
    key = "|".join([
        task.get("chat", ""),
        task.get("topic") or "",
        task["due"].strftime("%Y-%m-%d %H:%M") if task.get("due") else "none",
        task.get("text", "")[:40],
    ])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def build_tasks(messages: list, now: datetime | None = None) -> list:
    """把消息 list 变成任务 list。"""
    if now is None:
        now = datetime.now()

    candidates = extract_candidates(messages)

    tasks = []
    for c in candidates:
        detail = parse_due_detail(c["text"], c["msg_time"])
        task = dict(c)
        task["topics"] = c.get("topics", [])
        task["topic"] = task["topics"][0] if task["topics"] else None
        task["due"] = detail["due"]
        task["due_source"] = detail["due_source"]
        task["explicit"] = detail["explicit"]
        task["ambiguous"] = detail["ambiguous"]
        task["time_explicit"] = detail["time_explicit"]
        task["superseded"] = False
        task["superseded_by"] = None
        task["origin"] = "rule"
        task["user_edited"] = False
        task["excluded"] = False
        task["done"] = False
        tasks.append(task)

    _apply_corrections(tasks)

    for t in tasks:
        t["status"] = _status(t, now)
        t["remaining"] = remaining_text(t["due"], now)
        t["needs_confirm"] = _needs_confirm(t)
        t["id"] = _make_id(t)

    return sort_tasks(tasks)


def _status(task: dict, now: datetime) -> str:
    if task["superseded"]:
        return "已作废"
    if task["is_correction"]:
        return "待确认"
    return status_of(task["due"], now)


def _needs_confirm(task: dict) -> bool:
    """是否建议人工确认。"""
    if task["superseded"]:
        return False
    if task["due"] is None:
        return True
    if task["ambiguous"] or task["is_vague"]:
        return True
    if task.get("confidence", 1.0) < 0.6:
        return True
    return False


def _topics_overlap(a: dict, b: dict) -> bool:
    ta, tb = set(a.get("topics") or []), set(b.get("topics") or [])
    if not ta or not tb:
        return False
    return bool(ta & tb)


def _apply_corrections(tasks: list) -> None:
    """处理"以……为准"：把更早、同主题的任务标成已作废。

    * 更正消息自身状态为"待确认"。
    * 同群内，主题有交集、时间更早的活动任务被标记 superseded。
    * 若更正消息没有可识别主题，退化到"同群、更早的最近一条"，避免误伤。
    """
    for t in tasks:
        if not is_correction(t["text"]):
            continue
        same_chat_earlier = [o for o in tasks if o is not t and o["chat"] == t["chat"]
                             and o["msg_time"] < t["msg_time"] and not o["superseded"]]
        if t.get("topics"):
            targets = [o for o in same_chat_earlier if _topics_overlap(o, t)]
        else:
            targets = sorted(same_chat_earlier, key=lambda o: o["msg_time"])[-1:]
        for old in targets:
            old["superseded"] = True
            old["superseded_by"] = t["index"]


def sort_tasks(tasks: list) -> list:
    """按截止时间从早到晚排序；无时间的排最后，作废的排更后面。"""
    far = datetime.max
    return sorted(
        tasks,
        key=lambda t: (
            1 if t["superseded"] else 0,
            t["due"] is None,
            t["due"] or far,
        ),
    )


def summarize(tasks: list) -> dict:
    """统计用于页面顶部的数字卡片。"""
    active = [t for t in tasks if not t["superseded"] and not t.get("excluded")]
    return {
        "total": len(active),
        "urgent": sum(1 for t in active if t["status"] == "紧急"),
        "soon": sum(1 for t in active if t["status"] == "即将"),
        "confirm": sum(1 for t in active if t["needs_confirm"]),
        "overdue": sum(1 for t in active if t["status"] == "已过期"),
        "superseded": sum(1 for t in tasks if t["superseded"]),
    }