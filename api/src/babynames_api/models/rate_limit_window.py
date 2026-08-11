import datetime
import uuid

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from babynames_api.db import Base


class RateLimitWindow(Base):
    __tablename__ = "rate_limit_windows"

    account_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    window_start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
