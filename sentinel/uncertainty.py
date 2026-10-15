"""工具 6：不确定性检测工具。

判断每条候选任务：
    * 信息是否不足（due 未知）
    * 是否需要 AI
    * 是否需要用户确认
"""


def needs_ai(task: dict) -> bool:
    if task.get("superseded") or task.get("excluded"):
        return False
    if task.get("due") is None:
        return True
    # 规则已给出时间，即使含糊也不交给 AI 覆盖（只提示用户确认）
    return False


def needs_confirm(task: dict) -> bool:
    if task.get("superseded"):
        return False
    if task.get("due") is None:
        return True
    if task.get("ambiguous") or task.get("is_vague"):
        return True
    if task.get("origin") == "ai":
        return True
    if task.get("confidence", 1.0) < 0.6:
        return True
    return False


def reason_of(task: dict) -> str:
    if task.get("superseded"):
        return "已被后续更正消息覆盖"
    if task.get("due") is None:
        return "缺少明确时间"
    if task.get("ambiguous"):
        return "时间表达含糊（未写年份或说法不明确）"
    if task.get("is_vague"):
        return "原文用词含糊（例如尽量、大概、待定）"
    if task.get("origin") == "ai":
        return "由 AI 推断，未经原文证实"
    if task.get("confidence", 1.0) < 0.6:
        return "关键词命中较弱，可能是误识别"
    return ""


def confidence_label(conf) -> str:
    if conf is None:
        return "未知"
    if conf >= 0.75:
        return "高"
    if conf >= 0.55:
        return "中"
    return "低"


def scan(tasks: list) -> dict:
    uncertain = []
    for t in tasks:
        if t.get("superseded"):
            continue
        if needs_confirm(t):
            uncertain.append({
                "id": t.get("id"),
                "topic": t.get("topic") or t.get("text", "")[:16],
                "chat": t.get("chat"),
                "reason": reason_of(t),
                "needs_ai": needs_ai(t),
            })
    return {
        "count": len(uncertain),
        "need_ai": sum(1 for u in uncertain if u["needs_ai"]),
        "items": uncertain,
    }