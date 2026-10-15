"""第 1 步：读取聊天记录文件，转成 list + dict 结构。

约定的一种简单 txt 格式，每行一条消息，用竖线 | 分隔 4 个字段：

    时间 | 发送人 | 群名 | 内容

例如：
    2026-10-14 09:12 | 助教-李 | 数据结构-2026秋 | 实验三报告下周日晚上12点前交

设计要点（升级版）：
    * parse_line 不再"悄悄丢弃"坏行，而是返回 (消息 | None, 原因)。
      原因用于在网页 / 报告里明确提示"第 N 行无法识别，为什么"。
    * 时间格式固定为 年-月-日 时:分，也兼容 年/月/日 与 年月日。
    * 兼容分隔符全角竖线 ｜ 和中文冒号，降低"导出的记录格式不统一"带来的失败。
"""

from datetime import datetime

# 允许的几种时间写法（按常见程度排序）
TIME_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y.%m.%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
)


def _normalize_line(line: str) -> str:
    """把全角分隔符统一成半角，方便按 | 切分。"""
    return (
        line.replace("｜", "|")
        .replace("：", ":")
        .replace("\u3000", " ")  # 全角空格
    )


def _parse_time(time_text: str):
    """把时间文本转成 datetime；转不了返回 None。"""
    text = time_text.strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_line(line: str):
    """把一行文本解析成一条消息。

    返回 (message, reason)：
        message : dict 或 None（None 表示这行没解析成功）
        reason  : 失败原因字符串；成功时为 ""
    """
    raw = line.rstrip("\n").rstrip("\r")
    stripped = raw.strip()

    if not stripped:
        return None, "空行"

    normalized = _normalize_line(stripped)
    parts = normalized.split("|")

    if len(parts) != 4:
        return None, f"字段数不是 4（实际 {len(parts)} 个）"

    time_text, sender, chat, text = (p.strip() for p in parts)

    msg_time = _parse_time(time_text)
    if msg_time is None:
        return None, f"时间格式无法识别：{time_text!r}"

    if not text:
        return None, "内容为空"

    return (
        {
            "msg_time": msg_time,
            "sender": sender,
            "chat": chat,
            "text": text,
        },
        "",
    )


def parse_lines(text: str):
    """解析整段文本。

    返回 (messages, problems)：
        messages : 成功解析的消息 list
        problems : [{"line_no", "line", "reason"}, ...] 无法识别的行
    """
    messages = []
    problems = []
    for i, line in enumerate(text.splitlines(), 1):
        msg, reason = parse_line(line)
        if msg is not None:
            messages.append(msg)
        else:
            # 空行不算"问题行"，不放进 problems，避免噪音
            if reason != "空行":
                problems.append({"line_no": i, "line": line.strip(), "reason": reason})
    return messages, problems


def read_chat_file(path: str):
    """读取一个聊天记录文件，返回 (messages, problems)。"""
    with open(path, "r", encoding="utf-8") as f:
        return parse_lines(f.read())


def read_many_files(paths: list):
    """读取多个文件，合并消息并按时间排序。

    返回 (messages, problems_and_sources)：
        messages             : 合并后的消息 list
        problems_and_sources : [{file, line_no, line, reason}, ...]
    """
    all_messages = []
    problems = []
    for path in paths:
        messages, probs = read_chat_file(path)
        all_messages.extend(messages)
        for p in probs:
            item = dict(p)
            item["file"] = path
            problems.append(item)

    all_messages.sort(key=lambda m: m["msg_time"])
    return all_messages, problems


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "data/demo_chat.txt"
    msgs, probs = read_chat_file(target)
    print(f"共读到 {len(msgs)} 条消息，{len(probs)} 行无法识别。\n")
    for i, m in enumerate(msgs):
        print(
            f"[{i}] {m['msg_time']:%Y-%m-%d %H:%M} | "
            f"{m['sender']} | {m['chat']} | {m['text']}"
        )
    for p in probs:
        print(f"  ! 第 {p['line_no']} 行：{p['reason']} -> {p['line']}")