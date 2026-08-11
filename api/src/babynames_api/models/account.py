import datetime
import uuid

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from babynames_api.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    deck_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    gender_filter: Mapped[str] = mapped_column(
        String, nullable=False, default="girl"
    )
    onboarded: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
