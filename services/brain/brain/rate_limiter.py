"""
rate_limiter.py — In-memory sliding window rate limiter.

JARVIS-GENERATED: False (human-authored foundation file)
"""
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: deque = deque()

    def allow(self) -> bool:
        now = time.time()
        while self._calls and self._calls[0] < now - self.window:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            return False
        self._calls.append(now)
        return True

    def remaining(self) -> int:
        now = time.time()
        while self._calls and self._calls[0] < now - self.window:
            self._calls.popleft()
        return max(0, self.max_calls - len(self._calls))
