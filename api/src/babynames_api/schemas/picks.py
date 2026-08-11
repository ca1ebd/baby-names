"""
Pydantic schemas for picks batch request/response.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PickItem(BaseModel):
    """A single pick in a batch."""

    slot: int = Field(ge=0, le=1, description="Swiper slot (0 or 1)")
    name: str = Field(min_length=1, max_length=100, description="Name string")
    verdict: str = Field(pattern="^(keep|no)$", description="keep or no")
    decidedAt: datetime = Field(
        description="Client-supplied timestamp for last-write-wins convergence"
    )


class PicksRequest(BaseModel):
    """Request body for POST /v1/picks."""

    picks: list[PickItem] = Field(
        max_length=500, description="Batch of picks, capped at 500"
    )


class SwiperPosition(BaseModel):
    """Recomputed swiper position after a picks flush."""

    slot: int
    position: int


class PicksResponse(BaseModel):
    """Response for POST /v1/picks."""

    accepted: int = Field(description="Number of picks processed")
    swipers: list[SwiperPosition] = Field(
        description="Recomputed positions so client doesn't have to guess"
    )
