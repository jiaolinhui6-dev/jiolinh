"""智能粘贴：把"老师发的一条消息"变成标准聊天记录格式。

使用场景（真实大学生的用法）：
    复制老师的消息 -> 粘贴 -> 点分析。

用户最少只要给出：
    1. 消息正文（必须）
    2. 发送人（可选，默认"老师"）
    3. 时间（可选，默认"现在"；也支持在正文里手写"今天/明天"等，或额外填一行）

本模块负责：
    * 从粘贴内容里尝试识别"发送人：" / "时间：" 这类标注；
    * 把裸消息补全成 `时间 | 发送人 | 群名 | 内容` 的标准行；
    * 保留原文，不篡改、不臆造。

设计原则：宁可少猜，也不乱猜。猜不到就用默认值并明确告诉用户。
"""

import re
from datetime import datetime, timedelta

# 识别 "发送人: xxx" / "老师: xxx" / "【xxx】" 等前缀
_SENDER_PATTERNS = [
    re.compile(r"^\s*(?:发送人|发件人|老师|助教|说话人)\s*[:：]\s*(.+?)\s*$"),
]

# 识别 "时间: 2026-10-14 09:12" / "2026-10-14 09:12" 这类时间行
_TIME_PATTERNS = [
    re.compile(r"^\s*(?:时间|发送时间|日期)\s*[:：]\s*(.+?)\s*$"),
    re.compile(r"^\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?(?:\s+\d{1,2}\s*[:：]\s*\d{2})?)\s*$"),
]

# QQ 客户端直接复制的消息头：`昵称: 09-28 08:12:04`
# 也兼容 `昵称：9-28 上午 8:12`、`昵称: 2026-09-28 08:12:04` 等写法。
_QQ_HEADER = re.compile(
    r"^\s*(?P<sender>[^:：]{1,40}?)\s*[:：]\s*"
    r"(?:(?P<ampm>凌晨|早上|上午|中午|下午|晚上|晚|早)\s*)?"
    r"(?:(?P<year>\d{4})\s*[-/年]\s*)?"
    r"(?P<month>\d{1,2})\s*[-/月]\s*(?P<day>\d{1,2})\s*日?\s*"
    r"(?P<hour>\d{1,2})\s*[:：]\s*(?P<minute>\d{1,2})"
    r"(?:\s*[:：]\s*(?P<second>\d{1,2}))?"
    r"\s*$"
)

# QQ 导出 txt / 复制内容里常见的元信息行，识别时直接跳过，避免当作正文
_META_JUNK_PATTERNS = [
    re.compile(r"^\s*=+\s*$"),
    re.compile(r"^\s*消息记录[（(]"),
    re.compile(r"^\s*消息分组\s*[:：]"),
    re.compile(r"^\s*消息对象\s*[:：]"),
    re.compile(r"^\s*[-—]{3,}\s*$"),
]

# QQ 导出 txt 的消息头：`2026-10-14 09:12:19 (助教-李)`
_QQ_EXPORT_HEADER = re.compile(
    r"^\s*(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})\s+"
    r"(?P<hour>\d{1,2})\s*[:：]\s*(?P<minute>\d{1,2})"
    r"(?:\s*[:：]\s*(?P<second>\d{1,2}))?"
    r"\s*(?:[(（](?P<sender>[^)）]*)[)）])?\s*$"
)

# 出现这些词说明是"正文里提到时间"，不是"消息头"，避免误判
_SENDER_REJECT_WORDS = ("时间", "截止", "日期", "提醒", "注意", "提交", "收取", "发放")

_TIME_FORMATS = (
    "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d",
    "%Y年%m月%d日", "%Y年%m月%d日 %H:%M",
)


def _parse_time(text: str):
    text = text.strip().replace("年", "年").replace("月", "月").replace("日", "日")
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    # 补一个"年月日"变体
    try:
        return datetime.strptime(text, "%Y年%m月%d日")
    except ValueError:
        return None


def _qq_header_time(m, now: datetime):
    """把 QQ 消息头里的日期时间补全成 datetime；不合法返回 None。"""
    year = int(m.group("year")) if m.group("year") else now.year
    month, day = int(m.group("month")), int(m.group("day"))
    hour, minute = int(m.group("hour")), int(m.group("minute"))
    second = int(m.group("second") or 0)
    ampm = (m.groupdict().get("ampm") or "").strip()
    if ampm in ("下午", "晚上", "晚", "中午") and hour < 12:
        hour += 12
    elif ampm == "凌晨" and hour == 12:
        hour = 0
    if not (1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and minute <= 59 and second <= 59):
        return None
    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
    # QQ 记录都是过去的消息；没写年份时，若算出来"还没到"，那就是去年的
    if m.group("year") is None and dt > now + timedelta(days=1):
        try:
            dt = dt.replace(year=year - 1)
        except ValueError:
            return None
    return dt


def _match_qq_header(stripped: str, now: datetime):
    """判断一行是不是 QQ 消息头。是则返回 (发送人, datetime)，否则返回 None。"""
    m = _QQ_HEADER.match(stripped)
    if m:
        sender = (m.group("sender") or "").strip()
        dt = _qq_header_time(m, now)
        if dt is not None and not any(w in sender for w in _SENDER_REJECT_WORDS):
            return sender, dt
    m2 = _QQ_EXPORT_HEADER.match(stripped)
    if m2:
        dt = _qq_header_time(m2, now)
        if dt is not None:
            return (m2.group("sender") or "").strip(), dt
    return None


def _is_junk_line(stripped: str) -> bool:
    return any(pat.match(stripped) for pat in _META_JUNK_PATTERNS)


def parse_qq_transcript(raw: str, *, chat: str, now: datetime, default_sender: str = "老师"):
    """把整段 QQ 聊天记录（复制或导出）切成多条消息。

    识别 `昵称: 09-28 08:12:04` 与 `2026-10-14 09:12:19 (助教-李)` 两种消息头，
    每个消息头之后到下一个消息头之前的行，都算作这条消息的正文。
    """
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = []
    cur = None
    for ln in text.split("\n"):
        stripped = ln.strip()
        if _is_junk_line(stripped):
            stripped = ""
        head = _match_qq_header(stripped, now) if stripped else None
        if head:
            if cur is not None:
                blocks.append(cur)
            cur = {"sender": head[0], "time": head[1], "body": []}
            continue
        if cur is not None:
            cur["body"].append(ln.rstrip())
    if cur is not None:
        blocks.append(cur)

    messages = []
    for b in blocks:
        body = "\n".join(b["body"]).strip()
        if not body:
            continue
        messages.append({
            "msg_time": b["time"],
            "sender": b["sender"] or default_sender,
            "chat": chat,
            "text": body,
        })
    return messages


def parse_smart_paste_batch(raw: str, *, default_sender: str = "老师",
                            default_chat: str = "我的课程群",
                            now: datetime | None = None):
    """智能粘贴的"批量版"：返回 (标准行列表, 提示列表)。

    * 已经是标准格式 -> 原样返回；
    * 像一整段 QQ 聊天记录（>=2 条）-> 自动拆成多条并各自补全；
    * 否则退回原来的"单条消息"逻辑。
    """
    if now is None:
        now = datetime.now()

    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    if sum(1 for ln in lines if ln.count("|") >= 3) >= 1:
        kept = [ln.strip() for ln in lines if ln.strip()]
        return kept, ["检测到标准格式（含竖线），已按标准聊天记录处理。"]

    msgs = parse_qq_transcript(raw, chat=default_chat, now=now)
    if len(msgs) >= 2:
        notes = [f"识别到 {len(msgs)} 条聊天记录（{msgs[0]['sender']} 等），已自动拆分并补全为标准格式。"]
        if any(not m["sender"] for m in msgs):
            notes.append(f"部分消息没有发送人，已默认用「{default_sender}」。")
        return [to_standard_line(m) for m in msgs], notes

    msg, notes = parse_smart_paste(raw, default_sender=default_sender,
                                   default_chat=default_chat, now=now)
    if msg is None:
        return [], notes
    return [to_standard_line(msg)], notes


def parse_smart_paste(raw: str, *, default_sender: str = "老师",
                      default_chat: str = "我的课程群",
                      now: datetime | None = None):
    """把一段"裸消息"解析成标准消息 dict。

    返回 (message, notes)：
        message : dict(msg_time, sender, chat, text) 或 None（内容为空时）
        notes   : 列表，说明哪些字段是自动补的，方便前端提示用户

    支持的输入形态：
        A. 只贴正文：
             实验三报告下周日晚上12点前交
        B. 带发送人：
             发送人: 李老师
             实验三报告下周日晚上12点前交
        C. 带时间和发送人：
             时间: 2026-10-14 09:12
             发送人: 李老师
             实验三报告下周日晚上12点前交
        D. 单行带竖线（已经是标准格式）：原样交给标准解析器
    """
    if now is None:
        now = datetime.now()

    notes = []
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln for ln in text.split("\n")]

    # D. 已经是标准格式（含竖线且能切 4 段）——直接不处理
    if sum(1 for ln in lines if ln.count("|") >= 3) >= 1:
        return None, ["检测到标准格式（含竖线），将按标准聊天记录解析。"]

    sender = None
    msg_time = None
    body_lines = []

    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue

        matched_meta = False
        for pat in _SENDER_PATTERNS:
            m = pat.match(stripped)
            if m:
                sender = m.group(1).strip()
                matched_meta = True
                break
        if matched_meta:
            continue

        if msg_time is None:
            for pat in _TIME_PATTERNS:
                m = pat.match(stripped)
                if m:
                    parsed = _parse_time(m.group(1))
                    if parsed:
                        msg_time = parsed
                        matched_meta = True
                        break
        if matched_meta:
            continue

        body_lines.append(stripped)

    body = "\n".join(body_lines).strip()
    if not body:
        return None, ["没有识别到消息正文，请把老师发的消息内容粘贴进来。"]

    if sender is None:
        sender = default_sender
        notes.append(f"未检测到发送人，已默认用「{sender}」，可在结果里修改。")
    if msg_time is None:
        msg_time = now
        notes.append(f"未检测到发送时间，已用当前时间「{msg_time:%Y-%m-%d %H:%M}」。")

    return {
        "msg_time": msg_time,
        "sender": sender,
        "chat": default_chat,
        "text": body,
    }, notes


def to_standard_line(message: dict) -> str:
    """把消息 dict 转回标准的一行（便于回填文本框 / 复用标准流程）。

    正文里的换行会被压成空格：标准格式要求"一行一条消息"，
    否则多行正文会把后续内容挤成无法解析的行。
    """
    body = re.sub(r"\s*\n+\s*", " ", str(message.get("text", ""))).strip()
    return (f"{message['msg_time']:%Y-%m-%d %H:%M} | {message['sender']} | "
            f"{message['chat']} | {body}")