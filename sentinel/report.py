"""第 4 步：把任务 list 整理成人能看懂的文本报告（命令行用）。

输出三部分：
    1. 按紧急程度排序的待办清单
    2. 每个群的课程安排汇总
    3. 被"以……为准"作废的旧消息（避免误交）
"""

from datetime import datetime


def _fmt_due(due) -> str:
    if due is None:
        return "未知"
    return due.strftime("%Y-%m-%d %H:%M")


def _fmt_msg_time(t: datetime) -> str:
    return t.strftime("%m-%d %H:%M")


def build_report(tasks: list, problems: list | None = None) -> str:
    """生成文本报告。problems 为无法识别的行（可选）。"""
    lines = []
    lines.append("=" * 62)
    lines.append("课程群 Deadline 哨兵 —— 任务报告")
    lines.append("生成时间：" + datetime.now().strftime("%Y-%m-%d %H:%M"))
    lines.append("=" * 62)
    lines.append("")

    active = [t for t in tasks if not t["superseded"] and not t.get("excluded")]
    lines.append(f"【一】待办清单（按紧急程度排序，共 {len(active)} 条）")
    lines.append("-" * 62)

    if not active:
        lines.append("（没有识别到任务，可能是聊天记录里没有 DDL，或规则需要补充）")
    for i, t in enumerate(active, 1):
        mark = ""
        if t.get("needs_confirm"):
            mark = "  ← 建议确认"
        lines.append(f"{i}. [{t['status']}] {t['topic'] or t['text'][:12]}{mark}")
        lines.append(f"   截止：{_fmt_due(t['due'])}（依据：{t['due_source']}）｜{t.get('remaining','')}")
        lines.append(f"   群：{t['chat']}｜发送人：{t['sender']}｜时间：{_fmt_msg_time(t['msg_time'])}")
        lines.append(f"   原文：{t['text']}")
        lines.append("")

    lines.append("【二】各群课程安排汇总")
    lines.append("-" * 62)
    chats: dict = {}
    for t in active:
        chats.setdefault(t["chat"], []).append(t)
    if not chats:
        lines.append("（无）")
    for chat, items in chats.items():
        lines.append(f"◆ {chat}（{len(items)} 条任务）")
        for t in items:
            topic = t["topic"] or t["text"][:12]
            lines.append(f"   - [{t['status']}] {topic}｜截止 {_fmt_due(t['due'])}")
        lines.append("")

    dead = [t for t in tasks if t["superseded"]]
    if dead:
        lines.append("【三】已作废的旧消息（被更正通知覆盖，别按这些交）")
        lines.append("-" * 62)
        for t in dead:
            lines.append(f"✗ {t['chat']}｜{_fmt_msg_time(t['msg_time'])}｜{t['text']}")
        lines.append("")

    if problems:
        lines.append(f"【四】无法识别的行（共 {len(problems)} 行）")
        lines.append("-" * 62)
        for p in problems:
            src = p.get("file", "")
            prefix = f"{src} " if src else ""
            lines.append(f"! {prefix}第 {p['line_no']} 行：{p['reason']} → {p['line']}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    from sentinel.read_chat import read_chat_file
    from sentinel.tasks import build_tasks

    messages, problems = read_chat_file("data/demo_chat.txt")
    print(build_report(build_tasks(messages), problems))