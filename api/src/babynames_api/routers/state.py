"""State endpoint - returns full account state"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from babynames_api.auth import get_current_user
from babynames_api.db import get_session
from babynames_api.models.account import Account
from babynames_api.models.name import Name
from babynames_api.models.pick import Pick
from babynames_api.models.swiper import Swiper
from babynames_api.ratelimit import check_rate_limit
from babynames_api.schemas.state import (
    AccountResponse,
    PickResponse,
    StateResponse,
    SwiperResponse,
)

router = APIRouter(prefix="/v1", tags=["state"])


@router.get("/state")
def get_state(
    account_id: Annotated[uuid.UUID, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> StateResponse:
    """Get full account state - account, swipers, and picks"""
    # Check rate limit
    check_rate_limit(account_id, session)

    # Get account
    account = session.get(Account, account_id)
    if not account:
        # Should not happen since get_current_user provisions it
        raise RuntimeError("Account not found after auth")

    # Get swipers
    swipers_stmt = select(Swiper).where(Swiper.account_id == account_id).order_by(Swiper.slot)
    swipers = session.scalars(swipers_stmt).all()

    # Get picks with name info
    picks_stmt = (
        select(Pick, Name)
        .join(Name, Pick.name_id == Name.id)
        .where(Pick.account_id == account_id)
        .order_by(Pick.slot, Pick.decided_at)
    )
    picks_with_names = session.execute(picks_stmt).all()

    # Build response
    return StateResponse(
        account=AccountResponse(
            lastName=account.last_name,
            genderFilter=account.gender_filter,
            onboarded=account.onboarded
        ),
        swipers=[
            SwiperResponse(
                slot=swiper.slot,
                label=swiper.label,
                position=swiper.position
            )
            for swiper in swipers
        ],
        picks=[
            PickResponse(
                slot=pick.slot,
                name=name.name,
                verdict=pick.verdict
            )
            for pick, name in picks_with_names
        ]
    )
