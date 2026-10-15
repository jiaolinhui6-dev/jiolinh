"""第 2 步：从聊天记录里挑出"可能是任务 / DDL"的消息。

完全不用 AI，只用"关键词规则"：
    一条消息里如果出现了任务类关键词，而且不像闲聊 / 广告，就把它当成候选任务。

升级点：
    * 区分"强关键词"（作业/截止/提交…）和"弱关键词"（当天/次日…），
      用命中情况给出 confidence（规则置信度）。
    * 标记 vague（表达含糊），供后续"待确认"提示使用。
    * 主题抽取支持"课程设计 / 课设 / 实验N / 第N次作业 / 论文"等更丰富的说法，
      并支持一条消息里出现多个主题（topics_of）。
"""

import re

# 出现这些词，说明消息"很可能"在说任务（强信号）
STRONG_KEYWORDS = [
    "交", "提交", "截止", "deadline", "DDL", "ddl",
    "作业", "实验", "报告", "小测", "考试", "期末", "期中",
    "报名", "选题", "答辩", "上台", "汇报", "pre", "presentation",
    "论文", "课设", "课程设计", "验收", "补交", "迟交",
]

# 时间 / 动作类弱信号：单独出现不足以判定，但能提高置信度
WEAK_KEYWORDS = ["前", "之前", "以前", "当天", "次日", "本周", "下周"]

# 兼容旧名字，方便老代码 / 老测试引用
TASK_KEYWORDS = STRONG_KEYWORDS

# 出现这些词，基本可以判定是闲聊 / 广告 / 提问，直接丢掉
NOISE_KEYWORDS = [
    "广告", "促销", "点击链接", "扫码", "收到", "好的", "谢谢",
    "哈哈", "有人知道", "怎么", "为什么", "？", "?", "在线等",
]

# "以……为准"这种消息，通常是在纠正前面说过的时间
CORRECTION_WORDS = ["为准"]

# 表达含糊、可能误识别的信号
VAGUE_WORDS = ["尽量", "可能", "大概", "左右", "看情况", "再说", "差不多", "待定", "另行通知"]

# 主题：第3次作业 / 实验一 / 课程设计 / 课设 / 论文 / 报告 …
TOPIC_PATTERNS = [
    re.compile(r"第\s*[一二三四五六七八九十\d]+\s*次\s*(?:作业|实验|报告|小测|论文|课设|课程设计)"),
    re.compile(r"(?:实验|作业|报告|小测|考试|论文)\s*[一二三四五六七八九十\d]{1,3}"),
    re.compile(r"(?:课程设计|课设)"),
]


def is_noise(text: str) -> bool:
    """这条消息是不是噪音（闲聊 / 广告 / 提问）？"""
    return any(word in text for word in NOISE_KEYWORDS)


def matched_keywords(text: str) -> list:
    """这条消息命中了哪些任务关键词（强 + 弱）。"""
    hits = [w for w in STRONG_KEYWORDS if w in text]
    hits += [w for w in WEAK_KEYWORDS if w in text]
    return hits


def strong_hits(text: str) -> list:
    return [w for w in STRONG_KEYWORDS if w in text]


def looks_like_task(text: str) -> bool:
    """这条消息看起来像任务 / DDL 吗？"""
    if is_noise(text):
        return False
    return len(strong_hits(text)) > 0


def is_correction(text: str) -> bool:
    """是不是"以……为准"这类更正消息？"""
    return all(word in text for word in CORRECTION_WORDS)


def is_vague(text: str) -> bool:
    """表达是否含糊（需要人工确认）？"""
    return any(word in text for word in VAGUE_WORDS)


def topics_of(text: str) -> list:
    """取出一条消息里出现的所有主题（去重、保持出现顺序）。"""
    found = []
    for pattern in TOPIC_PATTERNS:
        for m in pattern.finditer(text):
            topic = re.sub(r"\s+", "", m.group(0))
            if topic not in found:
                found.append(topic)
    return found


def topic_of(text: str):
    """取出一条消息的第一个主题；取不到返回 None。"""
    topics = topics_of(text)
    return topics[0] if topics else None


def confidence_of(text: str) -> float:
    """给候选任务打个规则置信度（0~1），用于"待确认"提示与排序。"""
    score = 0.4
    strong = strong_hits(text)
    if strong:
        score += min(0.3, 0.1 * len(strong))
    if any(w in text for w in ("截止", "交", "提交", "deadline", "DDL", "ddl")):
        score += 0.15
    if is_vague(text):
        score -= 0.25
    return max(0.0, min(1.0, round(score, 2)))


def extract_candidates(messages: list) -> list:
    """从消息 list 里挑出候选任务消息。

    每条候选比原消息多几个字段：
        matched        : 命中的关键词
        topics         : 命中的所有主题
        is_correction  : 是不是"以……为准"更正消息
        is_vague       : 表达是否含糊
        confidence     : 规则置信度
        index          : 在原始消息里的序号（保证可追溯）
    """
    tasks = []
    for idx, msg in enumerate(messages):
        text = msg["text"]
        if not looks_like_task(text):
            continue
        task = dict(msg)
        task["matched"] = matched_keywords(text)
        task["topics"] = topics_of(text)
        task["is_correction"] = is_correction(text)
        task["is_vague"] = is_vague(text)
        task["confidence"] = confidence_of(text)
        task["index"] = idx
        tasks.append(task)
    return tasks