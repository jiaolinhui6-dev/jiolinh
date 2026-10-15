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
from datetime import datetime

# 识别 "发送人: xxx" / "老师: xxx" / "【xxx】" 等前缀
_SENDER_PATTERNS = [
    re.compile(r"^\s*(?:发送人|发件人|老师|助教|说话人)\s*[:：]\s*(.+?)\s*$"),
]

# 识别 "时间: 2026-10-14 09:12" / "2026-10-14 09:12" 这类时间行
_TIME_PATTERNS = [
    re.compile(r"^\s*(?:时间|发送时间|日期)\s*[:：]\s*(.+?)\s*$"),
    re.compile(r"^\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?(?:\s+\d{1,2}\s*[:：]\s*\d{2})?)\s*$"),
]

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
    """把消息 dict 转回标准的一行（便于回填文本框 / 复用标准流程）。"""
    return (f"{message['msg_time']:%Y-%m-%d %H:%M} | {message['sender']} | "
            f"{message['chat']} | {message['text']}")