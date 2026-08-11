"""
Pydantic schemas for deck endpoints.
"""

from pydantic import BaseModel, Field


class DeckNextRequest(BaseModel):
    """Request schema for POST /v1/deck/next."""

    slot: int = Field(..., ge=0, le=1, description="Swiper slot (0 or 1)")
    count: int = Field(
        ..., description="Number of names to request (will be clamped to 1-200)"
    )


class DeckCard(BaseModel):
    """A single card in the deck."""

    position: int = Field(..., description="0-based position in the account's served order")
    name: str = Field(..., description="The name")
    gender: str = Field(..., description="'girl' or 'boy'")


class DeckNextResponse(BaseModel):
    """Response schema for POST /v1/deck/next."""

    block: list[DeckCard] = Field(..., description="The dealt block of names")
    exhausted: bool = Field(..., description="True if the corpus is exhausted for this filter")
