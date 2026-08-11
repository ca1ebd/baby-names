from sqlalchemy import CheckConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from babynames_api.db import Base


class Name(Base):
    __tablename__ = "names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    gender: Mapped[str] = mapped_column(String, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    is_core: Mapped[bool] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("gender", "rank", name="uq_names_gender_rank"),
        CheckConstraint("gender IN ('girl', 'boy')", name="ck_names_gender"),
        Index("ix_names_gender_rank", "gender", "rank"),
    )
