"""
Assembling the full account state.

`GET /v1/state` and `POST /v1/reset` return the same body by contract — reset's
whole job is to hand back the state that now exists — so both read it from here
rather than each building the shape and drifting apart.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from babynames_api.models.account import Account
from babynames_api.models.name import Name
from babynames_api.models.pick import Pick
from babynames_api.models.swiper import Swiper
from babynames_api.schemas.state import (
    AccountResponse,
    PickResponse,
    StateResponse,
    SwiperResponse,
)


def load_state(session: Session, account_id: uuid.UUID) -> StateResponse:
    """Everything needed to restore a signed-in user on a fresh device (FR-007)."""
    account = session.get(Account, account_id)
    if not account:
        # get_current_user provisions the account, so this is unreachable in a
        # served request — it only fires if auth was bypassed.
        raise RuntimeError("Account not found after auth")

    swipers_stmt = select(Swiper).where(Swiper.account_id == account_id).order_by(Swiper.slot)
    swipers = session.scalars(swipers_stmt).all()

    # Picks are returned in full rather than paged (contracts/http-api.md).
    picks_stmt = (
        select(Pick, Name)
        .join(Name, Pick.name_id == Name.id)
        .where(Pick.account_id == account_id)
        .order_by(Pick.slot, Pick.decided_at)
    )
    picks_with_names = session.execute(picks_stmt).all()

    return StateResponse(
        account=AccountResponse(
            lastName=account.last_name,
            genderFilter=account.gender_filter,
            onboarded=account.onboarded,
        ),
        swipers=[
            SwiperResponse(slot=swiper.slot, label=swiper.label, position=swiper.position)
            for swiper in swipers
        ],
        picks=[
            PickResponse(
                slot=pick.slot,
                name=name.name,
                verdict=pick.verdict,
                decidedAt=pick.decided_at,
            )
            for pick, name in picks_with_names
        ],
    )
