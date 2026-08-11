"""Pydantic schemas for state, settings, and reset endpoints"""
import datetime

from pydantic import BaseModel, field_serializer


class AccountResponse(BaseModel):
    lastName: str
    genderFilter: str
    onboarded: bool


class SwiperResponse(BaseModel):
    slot: int
    label: str
    position: int


class PickResponse(BaseModel):
    slot: int
    name: str
    verdict: str
    decidedAt: datetime.datetime

    @field_serializer("decidedAt")
    def serialize_decided_at(self, value: datetime.datetime) -> str:
        """
        Render `decidedAt` exactly as JavaScript's `Date.toISOString()` does.

        The client round-trips this value straight back into POST /v1/picks as
        the last-write-wins tiebreak, so the string it reads has to be the same
        string it would have produced locally — millisecond precision, `Z`, no
        `+00:00` offset form.
        """
        utc_value = value.astimezone(datetime.UTC)
        return f"{utc_value.strftime('%Y-%m-%dT%H:%M:%S')}.{utc_value.microsecond // 1000:03d}Z"


class StateResponse(BaseModel):
    account: AccountResponse
    swipers: list[SwiperResponse]
    picks: list[PickResponse]


class SettingsRequest(BaseModel):
    lastName: str
    genderFilter: str
    onboarded: bool
    swiper0Label: str
    swiper1Label: str


class ResetRequest(BaseModel):
    scope: str  # "everything" or "swiper"
    slot: int | None = None  # Required if scope is "swiper"
