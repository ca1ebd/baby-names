"""
Deck router: POST /v1/deck/next
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from babynames_api.auth import get_current_user
from babynames_api.db import get_session
from babynames_api.deck import deal_block
from babynames_api.models.account import Account
from babynames_api.ratelimit import check_rate_limit
from babynames_api.schemas.deck import DeckCard, DeckNextRequest, DeckNextResponse

router = APIRouter(prefix="/v1", tags=["deck"])


@router.post("/deck/next", response_model=DeckNextResponse)
async def deck_next(
    request: DeckNextRequest,
    db: Session = Depends(get_session),
    account_id: str = Depends(get_current_user),
    _rate_limit: None = Depends(check_rate_limit),
):
    """
    Deal the next block of names for a swiper.

    Returns names from the swiper's current position onward. If the requested
    run extends past the end of served_order, deals more names first by running
    the account-seeded weighted shuffle.

    The block honors the account's gender_filter and never repeats a name (FR-015).
    """
    # Get account to access gender_filter and deck_seed
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError(f"Account not found: {account_id}")

    # Deal the block
    block, exhausted = deal_block(
        db=db,
        account_id=account_id,
        slot=request.slot,
        count=request.count,
        gender_filter=account.gender_filter,
        deck_seed=account.deck_seed,
    )

    # Convert to DeckCard objects
    cards = [DeckCard(**card) for card in block]

    return DeckNextResponse(block=cards, exhausted=exhausted)
