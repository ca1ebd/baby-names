"""Settings endpoint - updates account and swiper data"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from babynames_api.auth import get_current_user
from babynames_api.db import get_session
from babynames_api.models.account import Account
from babynames_api.models.swiper import Swiper
from babynames_api.ratelimit import check_rate_limit
from babynames_api.schemas.state import SettingsRequest, StateResponse
from babynames_api.state import load_state

router = APIRouter(prefix="/v1", tags=["settings"])


@router.put("/settings")
def update_settings(
    settings: SettingsRequest,
    account_id: Annotated[uuid.UUID, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    _rate_limit: Annotated[None, Depends(check_rate_limit)],
) -> StateResponse:
    """
    Update account settings and swiper labels.

    Returns the updated account and swipers. Changing genderFilter deliberately
    does not rewrite served_order: already-dealt names keep their positions and
    the filter applies to names dealt from here on (contracts/http-api.md).
    """
    # Update account
    account = session.get(Account, account_id)
    if not account:
        raise RuntimeError("Account not found after auth")

    account.last_name = settings.lastName
    account.gender_filter = settings.genderFilter
    account.onboarded = settings.onboarded

    # Update swiper labels
    swiper0 = session.scalars(
        select(Swiper).where(Swiper.account_id == account_id, Swiper.slot == 0)
    ).first()
    swiper1 = session.scalars(
        select(Swiper).where(Swiper.account_id == account_id, Swiper.slot == 1)
    ).first()

    if swiper0:
        swiper0.label = settings.swiper0Label
    if swiper1:
        swiper1.label = settings.swiper1Label

    session.commit()

    return load_state(session, account_id)
