"""网页应用：课程 Deadline 哨兵。

只用 Python 自带的 http.server，不需要第三方依赖。

运行（在项目根目录 deadline-sentinel 下）：
    python webapp.py                       # 默认只监听本机 127.0.0.1:8000
    HOST=0.0.0.0 python webapp.py          # 对外监听（配合隧道/反向代理放到公网）
    PORT=8080 python webapp.py             # 换端口

三种 AI 模式（网页里切换）：
    * 官方演示  —— 作者提供的 DEMO_* Key，供访客体验；有每 IP / 每日限流保护额度
    * 我的 API  —— 访客填自己的 Base URL / Key / Model，只存访客浏览器本地，
                    每次请求随请求体带上来；服务端不保存、也看不到任何访客的 Key
    * 离线      —— 只用规则，不联网，零费用

安全约定：
    * 默认只监听 127.0.0.1；要对外服务需显式设置 HOST 环境变量，或改本文件 HOST。
    * 对外服务建议：用 cloudflared/ngrok 等隧道（自带 HTTPS），不要裸奔 HTTP。
    * 请求体大小有限制（默认 1MB）。
    * 不写日志文件、不在响应中泄露 API Key。
    * 官方演示模式的 AI 调用有限流（每 IP / 每日上限），防止额度被单人刷完。
"""

import json
import os
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from sentinel.ratelimit import RateLimiter

from sentinel.read_chat import parse_lines
from sentinel.tasks import build_tasks, summarize
from sentinel import agent as agent_core
from sentinel import api_config
from sentinel import export as exporter
from sentinel import ai_helper
from sentinel.page import PAGE_HTML
from sentinel.paste_import import parse_smart_paste, to_standard_line

# 监听地址：本机默认只绑 127.0.0.1。
# 云平台（Render/Railway/Fly 等）会注入 PORT 环境变量，此时默认绑 0.0.0.0，
# 否则平台扫不到端口、部署会失败。也可随时用 HOST 环境变量显式覆盖。
_port_env = os.environ.get("PORT")
HOST = os.environ.get("HOST", "").strip() or ("0.0.0.0" if _port_env else "127.0.0.1")
PORT = int(_port_env or "8000")
MAX_BODY = 1 * 1024 * 1024  # 1MB 请求上限
DEMO_PATH = "data/demo_chat.txt"
SAMPLE_PATH = "data/sample_chat.txt"
MAX_AI_CALLS = 5            # 单次分析最多发给模型的候选条数上限

# 官方演示模式的限流（可用环境变量调整）
DEMO_AI_PER_IP_PER_MIN = int(os.environ.get("DEMO_AI_PER_IP_PER_MIN", "6") or "6")
DEMO_AI_GLOBAL_PER_DAY = int(os.environ.get("DEMO_AI_GLOBAL_PER_DAY", "200") or "200")
_limiter = RateLimiter(per_ip_per_min=DEMO_AI_PER_IP_PER_MIN,
                       global_per_day=DEMO_AI_GLOBAL_PER_DAY)


# 启动时尝试加载项目根目录的 .env（若存在），让 BASE_URL/API_KEY/MODEL 生效
ai_helper.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def load_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _custom_from_body(body: dict) -> dict | None:
    """从请求体取访客自己填的 API 配置。

    有 api_key 才认作"访客自带配置"；返回 None 表示让服务端按默认逻辑（环境变量）。
    这样可确保访客永远不会误用作者本机 .env 里的 Key。
    """
    if not isinstance(body, dict):
        return None
    api_key = str(body.get("api_key", "") or "").strip()
    if not api_key:
        return None
    return {
        "base_url": str(body.get("base_url", "") or "").strip(),
        "api_key": api_key,
        "model": str(body.get("model", "") or "").strip(),
    }


def analyze_text(text: str, use_ai: bool, now: datetime | None = None) -> dict:
    """核心分析流程：解析 -> 建任务 -> （可选）AI 增强。"""
    if now is None:
        now = datetime.now()

    messages, problems = parse_lines(text)
    tasks = build_tasks(messages, now=now)

    ai_meta = {"enabled": ai_helper.is_enabled(), "used": False, "error": "", "candidates": 0}
    if use_ai:
        suggestions, meta = ai_helper.suggest_for_tasks(
            tasks, now, max_calls=MAX_AI_CALLS
        )
        ai_meta = meta
        apply_ai_suggestions(tasks, suggestions, now)
    else:
        ai_meta["error"] = "未勾选 AI 增强，本次仅使用规则引擎。"

    # 重新计算状态（AI 可能补了截止时间）
    for t in tasks:
        from sentinel.ddl import status_of, remaining_text
        if t["superseded"]:
            t["status"] = "已作废"
        elif t["is_correction"]:
            t["status"] = "待确认"
        else:
            t["status"] = status_of(t["due"], now)
        t["remaining"] = remaining_text(t["due"], now)
        if t.get("origin") == "ai" and t["due"] is not None:
            t["needs_confirm"] = True   # AI 推断必须人工确认
    from sentinel.tasks import sort_tasks
    tasks = sort_tasks(tasks)

    return {
        "ok": True,
        "now": now.strftime("%Y-%m-%d %H:%M"),
        "tasks": [serialize_task(t) for t in tasks],
        "summary": summarize(tasks),
        "problems": problems,
        "ai": ai_meta,
    }


def apply_ai_suggestions(tasks: list, suggestions: list, now: datetime) -> None:
    """把 AI 建议写回任务：只补"未知/待确认"的截止时间，标记 origin=ai，不覆盖原文。"""
    by_id = {t["id"]: t for t in tasks}
    for s in suggestions:
        t = by_id.get(s["id"])
        if t is None:
            continue
        if t["superseded"]:
            continue
        if s["due"] is None:
            continue
        t["due"] = s["due"]
        t["due_source"] = "AI 推断（需确认）" + (f"：{s['reason']}" if s.get("reason") else "")
        t["explicit"] = False
        t["ambiguous"] = True
        t["origin"] = "ai"
        t["needs_confirm"] = True


def serialize_task(t: dict) -> dict:
    """把任务对象转成前端可用的 JSON（datetime -> 字符串，不含任何密钥）。"""
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
        "origin": t.get("origin", "rule"),
        "done": bool(t.get("done")),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "DeadlineSentinel/2.0"

    # ---------- 基础工具 ----------
    def _send(self, body, status: int = 200, content_type: str = "text/html; charset=utf-8",
              extra_headers: dict | None = None):
        # body 可以是 str（按 utf-8 编码）或 bytes（原样发送，用于 XLSX / 带 BOM 的 CSV）
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    # ---------- 静态资源 ----------
    STATIC_TYPES = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
    }
    ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

    def _serve_static(self, path: str):
        """只服务 assets/ 下的文件；做路径穿越防护。"""
        rel = urllib.parse.unquote(path[len("/assets/"):])
        target = os.path.normpath(os.path.join(self.ASSETS_DIR, rel))
        if not target.startswith(self.ASSETS_DIR + os.sep):
            self._send("Not Found", 404, "text/plain; charset=utf-8")
            return
        if not os.path.isfile(target):
            self._send("Not Found", 404, "text/plain; charset=utf-8")
            return
        ext = os.path.splitext(target)[1].lower()
        ctype = self.STATIC_TYPES.get(ext, "application/octet-stream")
        try:
            with open(target, "rb") as f:
                data = f.read()
        except OSError:
            self._send("Read Error", 500, "text/plain; charset=utf-8")
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    def _client_ip(self) -> str:
        """取客户端 IP：优先 X-Forwarded-For（隧道/反代），否则用套接字地址。"""
        xff = self.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "unknown"

    def _json(self, obj: dict, status: int = 200):
        self._send(json.dumps(obj, ensure_ascii=False), status, "application/json; charset=utf-8")

    def _read_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            return None
        raw = self.rfile.read(length).decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    # ---------- 路由 ----------
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send(PAGE_HTML)
        elif path.startswith("/assets/"):
            self._serve_static(path)
        elif path == "/api/demo":
            self._json({"text": load_text_file(SAMPLE_PATH) or load_text_file(DEMO_PATH)})
        elif path == "/api/agent_config":
            self._json({"ok": True, "status": api_config.status(), "rate": _limiter.stats()})
        elif path == "/api/ai_status":
            cfg = ai_helper.get_config()
            self._json({
                "enabled": cfg["enabled"],
                "model": cfg["model"],
                "base_url": cfg["base_url"],
                "key_masked": ai_helper.mask_key(cfg["api_key"]),
            })
        else:
            self._json({"ok": False, "error": "未知路径"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self._read_body()
        if body is None:
            self._json({"ok": False, "error": "请求体过大（上限 1MB）"}, 413)
            return

        if path == "/api/analyze":
            text = str(body.get("text", ""))
            if not text.strip():
                self._json({"ok": False, "error": "内容为空"}, 400)
                return
            use_ai = bool(body.get("use_ai"))
            try:
                self._json(analyze_text(text, use_ai))
            except Exception as e:  # 绝不让单次异常打崩服务
                self._json({"ok": False, "error": f"分析出错：{e}"}, 500)
        elif path == "/api/agent_config":
            self._json({"ok": True, "status": api_config.status(), "rate": _limiter.stats()})
        elif path == "/api/agent_test":
            # 测试连接：用当前选定的模式做一次最小调用
            mode = str(body.get("mode", "offline") or "offline")
            cfg = api_config.effective_config(mode, custom=_custom_from_body(body))
            if not cfg["enabled"]:
                self._json({"ok": False, "error": f"{mode} 模式配置不完整（缺 Base URL / Key / Model）。"}, 400)
                return
            if mode == "demo":
                allowed, why = _limiter.check(self._client_ip())
                if not allowed:
                    self._json({"ok": False, "error": why}, 429)
                    return
            try:
                ok, msg = agent_core.test_connection(cfg)
                self._json({"ok": ok, "message": msg, "model": cfg["model"]})
            except Exception as e:
                self._json({"ok": False, "error": f"测试失败：{e}"}, 500)
        elif path == "/api/agent_config_save":
            # 兼容旧前端：不再在服务端保存任何访客配置，只回脱敏状态
            self._json({"ok": True, "status": api_config.status()})
        elif path == "/api/agent_config_clear":
            self._json({"ok": True, "status": api_config.status()})
        elif path == "/api/agent":
            text = str(body.get("text", "") or "")
            if not text.strip():
                self._json({"ok": False, "error": "内容为空"}, 400)
                return
            mode = str(body.get("mode", "offline") or "offline")
            # 仅"官方演示"模式受额度保护；离线与自带 Key 不受限
            if mode == "demo":
                allowed, why = _limiter.check(self._client_ip())
                if not allowed:
                    self._json({"ok": False, "error": why, "rate_limited": True}, 429)
                    return
            try:
                self._json(agent_core.run_agent(text, mode=mode, max_ai_calls=MAX_AI_CALLS,
                                                custom=_custom_from_body(body)))
            except Exception as e:
                self._json({"ok": False, "error": f"分析出错：{e}"}, 500)
        elif path == "/api/smart_paste":
            # 智能粘贴：把老师的一条消息补全成标准格式，返回给前端回填
            raw = str(body.get("text", "") or "")
            if not raw.strip():
                self._json({"ok": False, "error": "没检测到内容，请把老师发的消息粘贴进来。"}, 400)
                return
            sender = str(body.get("sender", "") or "").strip() or "老师"
            chat = str(body.get("chat", "") or "").strip() or "我的课程群"
            msg, notes = parse_smart_paste(raw, default_sender=sender, default_chat=chat)
            if msg is None:
                self._json({"ok": False, "error": "；".join(notes) or "无法识别这段内容。"}, 400)
                return
            self._json({
                "ok": True,
                "standard_line": to_standard_line(msg),
                "sender": msg["sender"],
                "chat": msg["chat"],
                "msg_time": msg["msg_time"].strftime("%Y-%m-%d %H:%M"),
                "text": msg["text"],
                "notes": notes,
            })
        elif path == "/api/export":
            fmt = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("format", ["json"])[0]
            tasks = body.get("tasks", []) or []
            if fmt == "csv":
                # 带 UTF-8 BOM，Excel 双击不乱码；附下载文件名
                self._send(exporter.to_csv_bytes(tasks),
                           content_type="text/csv; charset=utf-8",
                           extra_headers={"Content-Disposition": 'attachment; filename="deadline-sentinel.csv"'})
            elif fmt == "xlsx":
                if not exporter.HAS_OPENPYXL:
                    self._json({"ok": False,
                                "error": "未安装 openpyxl，无法导出 Excel。请运行 pip install openpyxl，或改用 CSV。"},
                               501)
                else:
                    self._send(exporter.to_xlsx(tasks),
                               content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               extra_headers={"Content-Disposition": 'attachment; filename="deadline-sentinel.xlsx"'})
            elif fmt == "json":
                self._send(exporter.to_json(tasks), content_type="application/json; charset=utf-8",
                           extra_headers={"Content-Disposition": 'attachment; filename="deadline-sentinel.json"'})
            else:
                self._json({"ok": False, "error": "不支持的导出格式"}, 400)
        else:
            self._json({"ok": False, "error": "未知路径"}, 404)

    def log_message(self, fmt, *args):
        pass  # 关掉默认访问日志，避免把聊天内容带进控制台


def main():
    print("=" * 58)
    print("课程 Deadline 哨兵 已启动")
    if HOST in ("127.0.0.1", "localhost"):
        print(f"请在浏览器打开： http://{HOST}:{PORT}")
        print("当前仅本机可访问。要对外服务请设 HOST=0.0.0.0（建议配合隧道）。")
    else:
        print(f"监听地址： http://{HOST}:{PORT}（已对外监听）")
        print("公网部署建议用 cloudflared / ngrok 隧道（自带 HTTPS）。")
    demo = api_config.demo_config()
    if demo["base_url"] and demo["api_key"] and demo["model"]:
        print(f"官方演示模式：已配置（模型 {demo['model']}）｜限流：每IP {DEMO_AI_PER_IP_PER_MIN}/分钟，"
              f"全局 {DEMO_AI_GLOBAL_PER_DAY}/天")
    else:
        print("官方演示模式：未配置（访客可用「我的 API」或「离线模式」）")
    print("=" * 58)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
