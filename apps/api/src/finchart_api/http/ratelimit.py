import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Sliding one-minute window per key. In-memory is enough for a single worker."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._limit = per_minute
        self._clock = clock
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= 60:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True
