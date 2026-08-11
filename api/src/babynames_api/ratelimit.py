import datetime
import uuid
from typing import Annotated

from fastapi import Depends, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from babynames_api.auth import get_current_user
from babynames_api.config import settings
from babynames_api.db import get_session
from babynames_api.errors import ApiError
from babynames_api.models.rate_limit_window import RateLimitWindow


def check_rate_limit(
    account_id: Annotated[uuid.UUID, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> None:
    """Check if account is within rate limit, raise 429 if exceeded"""
    now = datetime.datetime.now(tz=datetime.UTC)
    window_start = now.replace(minute=0, second=0, microsecond=0)

    # Count the request and read the new total in one statement. The counter
    # lives in Postgres precisely because more than one replica may be serving
    # this account (data-model.md), so a read-then-write would both lose
    # increments and collide on the primary key when two requests arrive at once.
    stmt = (
        insert(RateLimitWindow)
        .values(
            account_id=account_id,
            window_start=window_start,
            request_count=1,
        )
        .on_conflict_do_update(
            index_elements=[RateLimitWindow.account_id, RateLimitWindow.window_start],
            set_={"request_count": RateLimitWindow.request_count + 1},
        )
        .returning(RateLimitWindow.request_count)
    )
    request_count = session.execute(stmt).scalar_one()

    # Commit the count before deciding: a rejected request still consumed a slot,
    # and rolling it back would let a client past the cap by retrying.
    session.commit()

    if request_count > settings.rate_limit_per_hour:
        # Calculate retry-after
        next_window = window_start + datetime.timedelta(hours=1)
        retry_after = int((next_window - now).total_seconds())

        raise ApiError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="rate_limited",
            message="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )
