import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from babynames_api.db import Base


class Swiper(Base):
    __tablename__ = "swipers"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("slot IN (0, 1)", name="ck_swipers_slot"),
    )
