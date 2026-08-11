import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from babynames_api.db import Base


class ServedOrder(Base):
    __tablename__ = "served_order"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_id: Mapped[int] = mapped_column(
        ForeignKey("names.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("account_id", "name_id", name="uq_served_order_account_name"),
    )
