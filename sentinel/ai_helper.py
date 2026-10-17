"""可选的大模型增强（OpenAI 兼容接口，标准库实现，无需第三方依赖）。

设计原则：
    * 用环境变量配置：BASE_URL / API_KEY / MODEL。
    * 只把"规则引擎搞不定"的消息发给模型，并附带最少必要上下文；
      不把整份聊天记录无脑外发。
    * AI 只产出"建议"，必须经过结构与日期校验；不能覆盖原始消息、不能伪造来源。
    * 单次分析有明确调用上限，避免重复请求浪费费用。
    * 任何失败（超时 / 网络 / 限流 / 无效响应 / 余额不足）都不影响规则结果。
"""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta

# 环境变量名
ENV_BASE_URL = "BASE_URL"
ENV_API_KEY = "API_KEY"
ENV_MODEL = "MODEL"

DEFAULT_TIMEOUT = 25


class AIError(Exception):
    """AI 调用相关的可读错误。"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind          # auth / network / timeout / rate_limit / balance / invalid / unknown
        self.message = message


def load_dotenv(path: str = ".env") -> bool:
    """从 .env 文件加载 BASE_URL / API_KEY / MODEL 到环境变量。

    * 只在环境变量尚未设置时才写入（真实环境变量优先于 .env）。
    * 找不到文件时静默返回 False。
    * 不打印、不记录任何密钥内容。

    返回是否成功读取到文件。
    """
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        return True
    except OSError:
        return False


def get_config() -> dict:
    """读取 AI 配置。未配置 API Key 时 enabled=False。"""
    base_url = (os.environ.get(ENV_BASE_URL) or "").strip().rstrip("/")
    api_key = (os.environ.get(ENV_API_KEY) or "").strip()
    model = (os.environ.get(ENV_MODEL) or "").strip()
    return {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "enabled": bool(api_key and base_url and model),
    }


def is_enabled() -> bool:
    return get_config()["enabled"]


def mask_key(key: str) -> str:
    """给日志/页面用的掩码，绝不暴露完整 Key。"""
    if not key:
        return "(未配置)"
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * 6 + key[-2:]


def _endpoint(base_url: str) -> str:
    """把 base_url 补成 chat/completions 端点。"""
    if base_url.endswith("/chat/completions"):
        return base_url
    return base_url + "/chat/completions"


def _default_transport(payload: dict, cfg: dict, timeout: int) -> dict:
    """真的发一次 HTTP 请求（标准库 urllib，不依赖 requests）。"""
    url = _endpoint(cfg["base_url"])
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        status = e.code
        if status in (401, 403):
            raise AIError("auth", f"鉴权失败（HTTP {status}），请检查 API_KEY。{detail}")
        if status == 429:
            raise AIError("rate_limit", f"请求被限流（HTTP 429），请稍后重试。{detail}")
        if status == 402 or "insufficient" in detail.lower() or "balance" in detail.lower():
            raise AIError("balance", f"余额不足或额度用完（HTTP {status}）。{detail}")
        raise AIError("network", f"服务返回错误（HTTP {status}）。{detail}")
    except urllib.error.URLError as e:
        raise AIError("network", f"网络连接失败：{e.reason}")
    except TimeoutError:
        raise AIError("timeout", f"请求超时（>{timeout}s）。")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise AIError("invalid", "AI 返回的不是合法 JSON。")


PROMPT_TEMPLATE = """你是一个中文课程待办解析助手。下面是从课程群聊天记录里挑出的、规则程序无法确定截止时间的消息。
请仅根据每条消息的原文（以及给出的参考"当前时间"）判断它的截止时间。

参考当前时间：{now}

严格要求：
1. 只输出 JSON 数组，**不要** Markdown 代码块、不要任何解释文字。
2. 结构：[{{"id": "<消息id>", "due": "YYYY-MM-DD HH:MM 或 null", "reason": "简述依据"}}]
3. 无法确定时必须给 null，不要编造。
4. 如果原文明确写了年份，照抄；只写月日的，按"离参考当前时间最近的未来时间"处理。
5. 不要修改、复述原文内容。
6. id 必须原样照抄消息列表里给出的 id，不要自己造。

示例输出（仅作格式参考）：
[{{"id": "示例id", "due": "2026-10-21 23:59", "reason": "原文提到下周三交"}}]

消息列表：
{messages}
"""


def select_tasks_for_ai(tasks: list) -> list:
    """挑出值得交给 AI 的消息：仅挑"规则完全无法确定截止时间"的。

    重要原则：规则已经能给出时间的任务，绝不送去给 AI（避免 AI 覆盖正确结果）。
    只挑 due is None 的，也就是规则真的搞不定的那些。
    """
    picked = []
    for t in tasks:
        if t.get("superseded") or t.get("excluded"):
            continue
        if t.get("due") is None:
            picked.append(t)
    return picked


def _build_prompt(picked: list, now: datetime, max_chars: int) -> str:
    lines = []
    for t in picked:
        line = f'- id={t["id"]} | 群：{t["chat"]} | 消息时间：{t["msg_time"]:%Y-%m-%d %H:%M} | 原文：{t["text"]}'
        lines.append(line)
    messages = "\n".join(lines)
    if len(messages) > max_chars:
        messages = messages[:max_chars] + "\n…（已截断，仅发送必要片段）"
    return PROMPT_TEMPLATE.format(now=now.strftime("%Y-%m-%d %H:%M"), messages=messages)


def _extract_json(content: str):
    """从模型回复里尽力抽出 JSON。

    实测中模型经常不按"只输出 JSON"来：可能包 ```json 代码块、前后带解释文字、
    或用 {"result": [...]} 之类的外层对象。这里做几层容错，仍然只接受能解析出来的结果。

    返回解析后的对象；全部失败时抛 AIError("invalid")。
    """
    if content is None:
        raise AIError("invalid", "AI 返回内容为空，已忽略。")
    text = str(content).strip()
    if not text:
        raise AIError("invalid", "AI 返回内容为空，已忽略。")

    # 1) 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) 去掉 Markdown 代码围栏（```json ... ``` / ``` ... ```）
    fence = re.search(r"```[a-zA-Z]*\s*(.+?)```", text, re.S)
    if fence:
        inner = fence.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            text = inner  # 继续往后面尝试从这段里截取

    # 3) 截取第一个 [ ... ] 或 { ... } 片段（模型常在 JSON 前后加解释）
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            snippet = text[start:end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                continue

    raise AIError("invalid", "AI 返回内容不是合法 JSON，已忽略。")


def _coerce_list(data):
    """把常见的"被包了一层"的结构摊平成列表。

    支持：直接的 list、{"result": [...]}、{"suggestions": [...]}、{"data": [...]}、
    以及只有单个对象 {@...} 的情况。找不到列表时返回 None。
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("result", "results", "suggestions", "data", "items", "list"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        # 单个建议对象（含 id）
        if "id" in data:
            return [data]
    return None


def _validate_suggestions(content: str, picked: list, now: datetime) -> list:
    """校验模型返回：必须是合法 JSON、id 必须来自本次输入、日期必须可解析且在合理范围。"""
    data = _extract_json(content)
    data = _coerce_list(data)
    if data is None:
        raise AIError("invalid", "AI 返回结构不是列表，已忽略。")

    valid_ids = {t["id"] for t in picked}
    by_id = {t["id"]: t for t in picked}
    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id", "")).strip()
        if tid not in valid_ids:
            continue  # 模型编造了不存在的 id，丢弃
        due_text = item.get("due")
        reason = str(item.get("reason", "")).strip()[:200]
        due = None
        if isinstance(due_text, str) and due_text.strip():
            parsed = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    parsed = datetime.strptime(due_text.strip(), fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                continue  # 日期无法解析，整条丢弃
            # 合理性校验：不能早于消息时间太多，也不能离谱地远
            if parsed < by_id[tid]["msg_time"] - timedelta(days=1):
                continue
            if parsed > now + timedelta(days=365 * 3):
                continue
            due = parsed
        results.append({"id": tid, "due": due, "reason": reason})
    return results


def suggest_for_tasks(
    tasks: list,
    now: datetime,
    *,
    max_calls: int = 5,
    max_chars: int = 4000,
    timeout: int = DEFAULT_TIMEOUT,
    transport=None,
    env: dict | None = None,
) -> tuple:
    """对"规则搞不定"的任务调用模型，返回 (suggestions, meta)。

    suggestions : [{id, due, reason}] —— 只是建议，调用方负责展示为"推断/待确认"。
    meta        : 本次调用的可读状态，用于页面提示与成本说明。

    transport 可注入假实现用于离线测试；env 可注入配置用于测试。
    """
    cfg = get_config()
    if env is not None:
        base_url = (env.get(ENV_BASE_URL) or "").strip().rstrip("/")
        api_key = (env.get(ENV_API_KEY) or "").strip()
        model = (env.get(ENV_MODEL) or "").strip()
        cfg = {"base_url": base_url, "api_key": api_key, "model": model,
               "enabled": bool(api_key and base_url and model)}

    meta = {
        "enabled": cfg["enabled"],
        "used": False,
        "calls": 0,
        "candidates": 0,
        "model": cfg["model"] if cfg["enabled"] else "",
        "error": "",
        "sent_scope": "",
    }

    if not cfg["enabled"]:
        meta["error"] = "未配置 BASE_URL / API_KEY / MODEL，AI 增强已跳过。"
        return [], meta

    picked = select_tasks_for_ai(tasks)
    meta["candidates"] = len(picked)
    if not picked:
        meta["error"] = "本次没有需要 AI 判断的任务（规则已能可靠处理）。"
        return [], meta

    # 调用上限：一次分析最多 max_calls 次请求，每次只发一批候选
    if len(picked) > max_calls * 5:
        picked = picked[: max_calls * 5]
    meta["sent_scope"] = f"仅发送 {len(picked)} 条待确认消息（及其群名、消息时间），未发送完整聊天记录。"

    prompt = _build_prompt(picked, now, max_chars)
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "你是严谨的中文课程待办解析助手。只输出 JSON 数组，不加代码块、不加解释。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }

    send = transport or _default_transport
    try:
        response = send(payload, cfg, timeout)
    except AIError as e:
        meta["error"] = f"AI 增强不可用：{e.message}"
        return [], meta
    except Exception as e:  # 兜底，绝不因 AI 崩掉主流程
        meta["error"] = f"AI 增强发生未知错误，已忽略：{e}"
        return [], meta

    meta["calls"] = 1
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        meta["error"] = "AI 返回结构不完整，已忽略。"
        return [], meta

    try:
        suggestions = _validate_suggestions(content, picked, now)
    except AIError as e:
        meta["error"] = e.message
        return [], meta

    meta["used"] = True
    if not suggestions:
        meta["error"] = "AI 未给出可用的截止时间建议。"
    return suggestions, meta