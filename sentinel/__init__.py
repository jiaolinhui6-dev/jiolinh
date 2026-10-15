"""课程 Deadline 哨兵（Deadline Sentinel）的核心代码包。

模块划分：
    read_chat.py  读聊天记录 -> 结构化消息
    extract.py    规则判断「像不像任务」
    ddl.py        规则解析截止时间 + 紧急程度
    tasks.py      组装最终任务对象（含去重、更正、置信度）
    report.py     命令行文本报告
    export.py     CSV / JSON 导出
    ai_helper.py  可选的大模型增强（OpenAI 兼容接口）
"""

__version__ = "2.0.0"