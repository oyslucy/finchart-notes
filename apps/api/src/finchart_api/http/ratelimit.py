import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Sliding window per key. In-memory is enough for a single worker."""

    def __init__(
        self, limit: int, window_s: float = 60, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_s
        self._clock = clock
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True
