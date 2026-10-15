"""工具 5：上下文检索工具。

作用：当某条消息看不懂时，去它附近找相关消息，帮忙判断。
只做检索，不改数据、不臆造。
"""


def window_context(messages: list, index: int, before: int = 2, after: int = 2) -> list:
    lo = max(0, index - before)
    hi = min(len(messages), index + after + 1)
    out = []
    for i in range(lo, hi):
        if i == index:
            continue
        m = messages[i]
        out.append({"index": i, "sender": m.get("sender", ""),
                    "text": m.get("text", ""), "msg_time": m.get("msg_time")})
    return out


def related_by_topic(messages: list, topics: list, chat: str, exclude_index: int,
                     limit: int = 4) -> list:
    if not topics:
        return []
    hits = []
    for i, m in enumerate(messages):
        if i == exclude_index or m.get("chat") != chat:
            continue
        text = m.get("text", "")
        if any(t and t in text for t in topics):
            hits.append({"index": i, "sender": m.get("sender", ""),
                         "text": text, "msg_time": m.get("msg_time")})
    return hits[-limit:]


def build_context(messages: list, index: int, topics: list, chat: str,
                  window: int = 2, limit: int = 5) -> list:
    merged = []
    seen = set()

    def _add(items):
        for it in items:
            key = (it["index"], it["text"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(it)

    _add(related_by_topic(messages, topics, chat, index, limit=limit))
    _add(window_context(messages, index, before=window, after=window))
    return merged[: limit + window * 2 + 1]


def format_context(lines: list, max_chars: int = 600) -> str:
    parts = []
    for it in lines:
        stamp = it["msg_time"].strftime("%m-%d %H:%M") if it.get("msg_time") else ""
        parts.append(f"[{stamp}] {it.get('sender','')}: {it.get('text','')}")
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text