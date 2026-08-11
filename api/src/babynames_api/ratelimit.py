import datetime
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from babynames_api.config import settings
from babynames_api.db import get_session
from babynames_api.models.rate_limit_window import RateLimitWindow


def check_rate_limit(
    account_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)]
) -> None:
    """Check if account is within rate limit, raise 429 if exceeded"""
    now = datetime.datetime.now(tz=datetime.UTC)
    window_start = now.replace(minute=0, second=0, microsecond=0)

    # Get or create rate limit window
    stmt = select(RateLimitWindow).where(
        RateLimitWindow.account_id == account_id,
        RateLimitWindow.window_start == window_start
    )
    window = session.scalar(stmt)

    if not window:
        window = RateLimitWindow(
            account_id=account_id,
            window_start=window_start,
            request_count=1
        )
        session.add(window)
        session.commit()
        return

    if window.request_count >= settings.rate_limit_per_hour:
        # Calculate retry-after
        next_window = window_start + datetime.timedelta(hours=1)
        retry_after = int((next_window - now).total_seconds())

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )

    window.request_count += 1
    session.commit()
