import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from babynames_api.db import Base


class Pick(Base):
    __tablename__ = "picks"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_id: Mapped[int] = mapped_column(
        ForeignKey("names.id", ondelete="RESTRICT"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(nullable=False)
    decided_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("slot IN (0, 1)", name="ck_picks_slot"),
        CheckConstraint("verdict IN ('keep', 'no')", name="ck_picks_verdict"),
    )
