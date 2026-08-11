import datetime
import uuid

import pytest
from fastapi import HTTPException

from babynames_api.ratelimit import check_rate_limit


def test_allows_requests_under_cap(db_session, monkeypatch):
    """Rate limiter should allow requests under the configured cap"""
    account_id = uuid.uuid4()

    # Set a low limit for testing
    from babynames_api import config
    monkeypatch.setattr(config.settings, "rate_limit_per_hour", 5)

    # Should allow 5 requests
    for _ in range(5):
        check_rate_limit(account_id, db_session)


def test_returns_429_when_exceeded(db_session, monkeypatch):
    """Rate limiter should return 429 with Retry-After when limit exceeded"""
    account_id = uuid.uuid4()

    from babynames_api import config
    monkeypatch.setattr(config.settings, "rate_limit_per_hour", 3)

    # Make 3 requests (at limit)
    for _ in range(3):
        check_rate_limit(account_id, db_session)

    # 4th request should raise 429
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(account_id, db_session)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) > 0


def test_resets_on_window_rollover(db_session, monkeypatch):
    """Rate limiter should reset on window rollover"""
    account_id = uuid.uuid4()

    from babynames_api import config
    from babynames_api.models.rate_limit_window import RateLimitWindow

    monkeypatch.setattr(config.settings, "rate_limit_per_hour", 2)

    # Create a window from the previous hour that's already at limit
    now = datetime.datetime.now(tz=datetime.UTC)
    prev_window_start = (now - datetime.timedelta(hours=1)).replace(
        minute=0, second=0, microsecond=0
    )

    prev_window = RateLimitWindow(
        account_id=account_id,
        window_start=prev_window_start,
        request_count=2
    )
    db_session.add(prev_window)
    db_session.commit()

    # Current window should allow new requests
    check_rate_limit(account_id, db_session)
    check_rate_limit(account_id, db_session)

    # 3rd request in current window should fail
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(account_id, db_session)

    assert exc_info.value.status_code == 429


def test_different_accounts_independent(db_session, monkeypatch):
    """Different accounts should have independent rate limits"""
    account_1 = uuid.uuid4()
    account_2 = uuid.uuid4()

    from babynames_api import config
    monkeypatch.setattr(config.settings, "rate_limit_per_hour", 2)

    # Account 1 uses up its limit
    check_rate_limit(account_1, db_session)
    check_rate_limit(account_1, db_session)

    with pytest.raises(HTTPException):
        check_rate_limit(account_1, db_session)

    # Account 2 should still be able to make requests
    check_rate_limit(account_2, db_session)
    check_rate_limit(account_2, db_session)
