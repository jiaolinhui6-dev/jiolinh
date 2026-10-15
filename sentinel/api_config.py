"""AI 配置中心：三种 API 模式 + 运行时配置。

模式：offline（离线）/ demo（项目演示 API）/ custom（用户自己的 API）。

安全约定：
    * 网页填的配置只存进程内存，不写项目文件、不写日志。
    * 服务重启后网页配置清空（可改用环境变量 / .env 持久化）。
    * 给网页的 Key 一律脱敏。
    * 演示 API 的 Key 只从环境变量读取，绝不写进源码或仓库。
"""

import os

from sentinel import ai_helper

VALID_MODES = ("offline", "demo", "custom")
_runtime: dict = {}


def demo_config() -> dict:
    return {
        "base_url": (os.environ.get("DEMO_BASE_URL") or "").strip().rstrip("/"),
        "api_key": (os.environ.get("DEMO_API_KEY") or "").strip(),
        "model": (os.environ.get("DEMO_MODEL") or "").strip(),
    }


def demo_available() -> bool:
    c = demo_config()
    return bool(c["base_url"] and c["api_key"] and c["model"])


def effective_config(mode: str, custom: dict | None = None) -> dict:
    """解析生效配置。

    custom 非 None 时用调用方提供的配置（网页端每访客自带、存浏览器本地），
    且绝不回退到服务端环境变量，避免访客误用作者的 Key。
    custom 为 None 时（CLI / 本机自用）才回退到进程内配置与环境变量。
    """
    mode = mode if mode in VALID_MODES else "offline"
    if mode == "demo":
        c = demo_config()
        return {"mode": "demo", "base_url": c["base_url"], "api_key": c["api_key"],
                "model": c["model"], "enabled": bool(c["base_url"] and c["api_key"] and c["model"])}
    if mode == "custom":
        if custom is not None:
            src = custom
            allow_env_fallback = False
        else:
            src = _runtime.get("custom", {})
            allow_env_fallback = True
        base_url = (src.get("base_url") or "").strip().rstrip("/")
        api_key = (src.get("api_key") or "").strip()
        model = (src.get("model") or "").strip()
        if allow_env_fallback and not (base_url and api_key and model):
            env = ai_helper.get_config()
            base_url = base_url or env["base_url"]
            api_key = api_key or env["api_key"]
            model = model or env["model"]
        return {"mode": "custom", "base_url": base_url, "api_key": api_key,
                "model": model, "enabled": bool(base_url and api_key and model)}
    return {"mode": "offline", "base_url": "", "api_key": "", "model": "", "enabled": False}


def set_custom(base_url: str, api_key: str, model: str) -> dict:
    _runtime["custom"] = {"base_url": (base_url or "").strip(),
                          "api_key": (api_key or "").strip(),
                          "model": (model or "").strip()}
    return status()


def clear_custom() -> dict:
    _runtime.pop("custom", None)
    return status()


def status() -> dict:
    demo = demo_config()
    custom = _runtime.get("custom", {})
    env = ai_helper.get_config()
    return {
        "demo": {"available": demo_available(), "model": demo["model"],
                 "base_url": demo["base_url"], "key_masked": ai_helper.mask_key(demo["api_key"])},
        "custom": {"configured": bool(custom.get("base_url") and custom.get("api_key") and custom.get("model")),
                   "model": custom.get("model", ""), "base_url": custom.get("base_url", ""),
                   "key_masked": ai_helper.mask_key(custom.get("api_key", ""))},
        "env": {"enabled": env["enabled"], "model": env["model"],
                "base_url": env["base_url"], "key_masked": ai_helper.mask_key(env["api_key"])},
    }
