from finchart_api.http.ratelimit import RateLimiter


def test_window_slides_after_a_minute() -> None:
    now = [0.0]
    limiter = RateLimiter(per_minute=2, clock=lambda: now[0])

    assert limiter.allow("u") and limiter.allow("u")
    assert not limiter.allow("u")
    now[0] = 60.0
    assert limiter.allow("u")
