"""Reset endpoint - clears account data"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from babynames_api.auth import get_current_user
from babynames_api.db import get_session
from babynames_api.models.account import Account
from babynames_api.models.pick import Pick
from babynames_api.models.served_order import ServedOrder
from babynames_api.models.swiper import Swiper
from babynames_api.ratelimit import check_rate_limit
from babynames_api.schemas.state import ResetRequest

router = APIRouter(prefix="/v1", tags=["reset"])


@router.post("/reset")
def reset_data(
    reset: ResetRequest,
    account_id: Annotated[uuid.UUID, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict[str, str]:
    """Reset account data - everything or single swiper"""
    # Check rate limit
    check_rate_limit(account_id, session)

    if reset.scope == "everything":
        # Clear all picks
        session.execute(delete(Pick).where(Pick.account_id == account_id))

        # Clear served order
        session.execute(delete(ServedOrder).where(ServedOrder.account_id == account_id))

        # Reset all swiper positions
        session.execute(
            Swiper.__table__.update()
            .where(Swiper.account_id == account_id)
            .values(position=0)
        )

        # Set onboarded to false
        account = session.get(Account, account_id)
        if account:
            account.onboarded = False

        session.commit()
        return {"status": "ok"}

    if reset.scope == "swiper":
        if reset.slot is None:
            raise HTTPException(status_code=400, detail="slot required for swiper scope")

        if reset.slot not in [0, 1]:
            raise HTTPException(status_code=400, detail="slot must be 0 or 1")

        # Clear picks for this slot only
        session.execute(
            delete(Pick).where(
                Pick.account_id == account_id,
                Pick.slot == reset.slot
            )
        )

        # Reset position for this swiper
        session.execute(
            Swiper.__table__.update()
            .where(Swiper.account_id == account_id, Swiper.slot == reset.slot)
            .values(position=0)
        )

        session.commit()
        return {"status": "ok"}

    raise HTTPException(status_code=400, detail="scope must be 'everything' or 'swiper'")
