"""Pydantic schemas for state, settings, and reset endpoints"""
from pydantic import BaseModel


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
