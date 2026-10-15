"""轻量限流：保护"官方演示 API"的额度不被一个人瞬间刷完。

设计：
    * 只对"演示/官方模式"的 AI 调用生效；离线模式和用户自带 Key 不受限。
    * 每 IP 每分钟次数限制 + 全局每日总次数限制。
    * 进程内存实现，单进程有效（本项目的部署方式足够）。

为什么需要：演示 Key 额度有限（例如 0.5 美元）。没有限流时，
一个人写个脚本几秒就能把额度刷完，后面的人都体验不到。
限流让额度更均匀地分给更多人。
"""

import threading
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, per_ip_per_min: int = 6, global_per_day: int = 200):
        self.per_ip_per_min = max(1, int(per_ip_per_min))
        self.global_per_day = max(1, int(global_per_day))
        self._ip_hits = defaultdict(list)
        self._day = ""
        self._day_count = 0
        self._lock = threading.Lock()

    def check(self, ip: str):
        """返回 (allowed, message)。"""
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        with self._lock:
            if self._day != today:
                self._day = today
                self._day_count = 0

            if self._day_count >= self.global_per_day:
                return False, f"今日官方演示额度已用完（上限 {self.global_per_day} 次）。请改选「离线模式」或「我的 API」。"

            hits = self._ip_hits[ip]
            hits[:] = [t for t in hits if now - t < 60]
            if len(hits) >= self.per_ip_per_min:
                return False, f"请求太频繁（每分钟最多 {self.per_ip_per_min} 次）。请稍后再试，或改用「离线模式」。"

            hits.append(now)
            self._day_count += 1
            return True, ""

    def stats(self) -> dict:
        with self._lock:
            return {"used_today": self._day_count, "daily_limit": self.global_per_day,
                    "per_ip_per_min": self.per_ip_per_min}