"""Agent 控制层：把工具串起来，并决定"是否需要 AI"。

架构：
    用户输入 -> Agent 控制层 -> Tools 工具层 -> LLM（按需）-> 结果输出

Agent 职责：判断是否需要 AI、调用工具、根据结果决定下一步、处理歧义、
判断是否需要用户确认、记录全过程 Trace。
"""

from datetime import datetime

from sentinel.read_chat import parse_lines
from sentinel.tasks import build_tasks, summarize
from sentinel.schedule import build_schedule
from sentinel import uncertainty
from sentinel import ai_helper
from sentinel import api_config


def serialize_task(t: dict) -> dict:
    return {
        "id": t.get("id"),
        "topic": t.get("topic"),
        "chat": t.get("chat"),
        "sender": t.get("sender"),
        "text": t.get("text"),
        "msg_time": t["msg_time"].strftime("%Y-%m-%d %H:%M") if t.get("msg_time") else "",
        "due": t["due"].strftime("%Y-%m-%d %H:%M") if t.get("due") else None,
        "due_source": t.get("due_source"),
        "remaining": t.get("remaining"),
        "status": t.get("status"),
        "explicit": bool(t.get("explicit")),
        "ambiguous": bool(t.get("ambiguous")),
        "needs_confirm": bool(t.get("needs_confirm")),
        "superseded": bool(t.get("superseded")),
        "excluded": bool(t.get("excluded")),
        "confidence": t.get("confidence"),
        "confidence_label": uncertainty.confidence_label(t.get("confidence")),
        "origin": t.get("origin", "rule"),
        "judge": "AI 辅助" if t.get("origin") == "ai" else "规则确认",
        "reason": uncertainty.reason_of(t),
        "source_index": t.get("index"),
        "done": bool(t.get("done")),
    }


def run_agent(text: str, *, mode: str = "offline", now: datetime | None = None,
              max_ai_calls: int = 5, transport=None, custom: dict | None = None) -> dict:
    """custom：访客自带的 API 配置（存浏览器本地、随请求传上来）。

    传了就只用它，不回退服务端环境变量，避免访客误用作者的 Key。
    """
    if now is None:
        now = datetime.now()

    trace = []

    def step(title, detail="", tool=""):
        trace.append({"step": len(trace) + 1, "title": title, "detail": detail, "tool": tool})

    messages, problems = parse_lines(text)
    step("读取聊天记录", f"解析出 {len(messages)} 条消息" + (f"，{len(problems)} 行无法识别" if problems else ""), "read_chat")
    if not messages:
        step("结束", "没有可分析的消息，请检查输入内容。")
        return _result(now, [], problems, _offline_meta(mode), trace, uncertainty.scan([]))

    tasks = build_tasks(messages, now=now)
    active = [t for t in tasks if not t["superseded"]]
    step("提取候选任务", f"发现 {len(active)} 条候选任务，其中 {sum(1 for t in tasks if t['superseded'])} 条被更正覆盖", "extract")

    resolved = [t for t in active if t["due"] is not None]
    step("解析截止时间并排序", f"{len(resolved)} 条已确定时间，按紧急程度排序", "ddl")

    scan = uncertainty.scan(tasks)
    step("检测不确定性", f"发现 {scan['count']} 条需要关注，其中 {scan['need_ai']} 条规则难以确定", "uncertainty")

    cfg = api_config.effective_config(mode, custom=custom)
    ai_meta = {"mode": mode, "enabled": cfg["enabled"], "used": False,
               "model": cfg["model"] if cfg["enabled"] else "",
               "base_url": cfg["base_url"] if cfg["enabled"] else "",
               "candidates": 0, "calls": 0, "error": "", "sent_scope": ""}

    if scan["need_ai"] == 0:
        step("判断", "所有任务规则都能确定，无需调用 AI")
        ai_meta["error"] = "本次没有需要 AI 判断的任务（规则已能可靠处理）。"
    elif mode == "offline":
        step("判断", "当前为离线模式，不调用 AI；困难任务标记为待确认")
        ai_meta["error"] = "离线模式：未调用 AI，困难任务已标记为待确认。"
    elif not cfg["enabled"]:
        step("判断", f"{mode} 模式配置不完整（缺 Base URL / Key / Model），回退到规则结果")
        ai_meta["error"] = f"{mode} 模式配置不完整，已回退到规则模式。"
    else:
        step("调用 AI 判断", f"把 {scan['need_ai']} 条困难任务（含必要上下文）发送给模型：{cfg['model']}", "llm")
        ai_meta["candidates"] = scan["need_ai"]
        try:
            suggestions, meta = ai_helper.suggest_for_tasks(
                tasks, now, max_calls=max_ai_calls,
                env={"BASE_URL": cfg["base_url"], "API_KEY": cfg["api_key"], "MODEL": cfg["model"]},
                transport=transport)
            ai_meta.update({"used": meta.get("used", False), "calls": meta.get("calls", 0),
                            "candidates": meta.get("candidates", ai_meta["candidates"]),
                            "error": meta.get("error", ""), "sent_scope": meta.get("sent_scope", "")})
            apply_ai_suggestions(tasks, suggestions, now)
            if ai_meta["used"]:
                step("AI 返回结果", f"模型给出 {len(suggestions)} 条建议，已标记为 AI 推断 · 需确认")
            else:
                step("AI 未产生建议", ai_meta["error"] or "无可用结果，保留规则结论")
        except Exception as e:
            ai_meta["error"] = f"AI 调用异常，已回退规则结果：{e}"
            step("AI 失败，回退规则", str(e))

    tasks = _refresh(tasks, now)
    step("生成最终结果", f"共 {summarize(tasks)['total']} 条待办，{scan['count']} 条需确认")
    return _result(now, tasks, problems, ai_meta, trace, scan)


def test_connection(cfg: dict, *, transport=None) -> tuple:
    """测试连接：发一条最小请求，验证 Base URL / Key / Model 是否可用。

    返回 (ok, message)。不发送任何聊天内容，只发一句 "ping"。
    """
    if not cfg.get("enabled"):
        return False, "配置不完整（缺 Base URL / Key / Model）。"
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    send = transport or ai_helper._default_transport
    try:
        resp = send(payload, cfg, 20)
    except ai_helper.AIError as e:
        return False, e.message
    except Exception as e:
        return False, f"连接失败：{e}"
    if isinstance(resp, dict) and resp.get("choices"):
        return True, "连接成功，模型可正常返回。"
    if isinstance(resp, dict) and resp.get("error"):
        return False, f"服务返回错误：{resp['error']}"
    return False, "服务返回内容不符合预期。"


def apply_ai_suggestions(tasks: list, suggestions: list, now: datetime) -> None:
    by_id = {t["id"]: t for t in tasks}
    for s in suggestions:
        t = by_id.get(s["id"])
        if t is None or t["superseded"] or s.get("due") is None:
            continue
        # 绝不覆盖规则已经确定的时间：只补"规则完全没给出时间"的任务
        if t.get("due") is not None:
            continue
        t["due"] = s["due"]
        t["due_source"] = "AI 推断（需确认）" + (f"：{s['reason']}" if s.get("reason") else "")
        t["explicit"] = False
        t["ambiguous"] = True
        t["origin"] = "ai"
        t["needs_confirm"] = True


def _refresh(tasks: list, now: datetime) -> list:
    from sentinel.ddl import status_of, remaining_text
    from sentinel.tasks import sort_tasks
    for t in tasks:
        if t["superseded"]:
            t["status"] = "已作废"
        elif t["is_correction"]:
            t["status"] = "待确认"
        else:
            t["status"] = status_of(t["due"], now)
        t["remaining"] = remaining_text(t["due"], now)
        t["needs_confirm"] = uncertainty.needs_confirm(t)
    return sort_tasks(tasks)


def _offline_meta(mode):
    return {"mode": mode, "enabled": False, "used": False, "model": "", "base_url": "",
            "candidates": 0, "calls": 0, "error": "", "sent_scope": ""}


def _result(now, tasks, problems, ai_meta, trace, scan) -> dict:
    """统一的返回结构。

    schedule 是"结构化时间表"，供网页的时间表视图和导出使用；
    这里直接用序列化过的 task，保证 JSON 可传输（datetime -> 字符串）。
    """
    return {"ok": True, "now": now.strftime("%Y-%m-%d %H:%M"),
            "tasks": [serialize_task(t) for t in tasks], "summary": summarize(tasks),
            "schedule": _serialize_schedule(build_schedule(tasks, now=now)),
            "problems": problems, "ai": ai_meta, "trace": trace, "uncertain": scan}


def _serialize_schedule(schedule: dict) -> dict:
    """时间表里的 items 含 datetime，转成 JSON 安全的 task 结构。"""
    out = dict(schedule)
    out["days"] = [
        {**d, "items": [serialize_task(t) for t in d.get("items", [])]}
        for d in schedule.get("days", [])
    ]
    out["buckets"] = [
        {**b, "items": [serialize_task(t) for t in b.get("items", [])]}
        for b in schedule.get("buckets", [])
    ]
    return out
