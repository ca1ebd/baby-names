"""
POST /v1/picks — batched upsert, recomputed swiper positions in the response.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from babynames_api.auth import get_current_user
from babynames_api.db import get_session
from babynames_api.models.name import Name
from babynames_api.models.pick import Pick
from babynames_api.models.served_order import ServedOrder
from babynames_api.models.swiper import Swiper
from babynames_api.ratelimit import check_rate_limit
from babynames_api.schemas.picks import (
    PickItem,
    PicksRequest,
    PicksResponse,
    SwiperPosition,
)

router = APIRouter(prefix="/v1/picks", tags=["picks"])


@router.post("", response_model=PicksResponse)
def post_picks(
    request: PicksRequest,
    account_id: Annotated[UUID, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    _rate_limit: Annotated[None, Depends(check_rate_limit)],
) -> PicksResponse:
    """
    Flush the offline outbox (FR-019, FR-020, FR-023).

    Behavior:
    - Idempotent by construction: upsert on (account_id, slot, name_id),
      keeping the row with the later decidedAt.
    - Accepts picks for names not in the swiper's current block.
    - Batches capped at 500 (enforced by schema).
    - Returns recomputed swiper positions.
    """

    # Resolve all names in the batch to their IDs.
    # A name the corpus does not know cannot be stored (picks reference names by
    # id) and cannot be re-sent to any better effect, so it is dropped rather
    # than rejected — the client only ever swipes names this service dealt it,
    # so this is the "can't happen" branch, not a routine one.
    name_strings = {pick.name for pick in request.picks}
    name_lookup: dict[str, int] = {}
    if name_strings:
        stmt = select(Name).where(Name.name.in_(name_strings))
        for name_row in session.execute(stmt).scalars():
            name_lookup[name_row.name] = name_row.id

    # Collapse the batch onto its own key first. An outbox can legitimately hold
    # the same name twice for one slot — swipe, undo, swipe again — and the two
    # entries are the same row, so the later decidedAt has to win here before
    # anything touches the database.
    latest_in_batch: dict[tuple[int, int], PickItem] = {}
    for pick in request.picks:
        name_id = name_lookup.get(pick.name)
        if name_id is None:
            continue

        key = (pick.slot, name_id)
        winner = latest_in_batch.get(key)
        if winner is None or pick.decidedAt > winner.decidedAt:
            latest_in_batch[key] = pick

    for (slot, name_id), pick in latest_in_batch.items():
        # Check if this pick already exists
        existing_stmt = select(Pick).where(
            and_(
                Pick.account_id == account_id,
                Pick.slot == slot,
                Pick.name_id == name_id,
            )
        )
        existing_pick = session.execute(existing_stmt).scalar_one_or_none()

        if existing_pick is not None:
            # Upsert: keep the row with the later decidedAt
            if pick.decidedAt > existing_pick.decided_at:
                existing_pick.verdict = pick.verdict
                existing_pick.decided_at = pick.decidedAt
        else:
            # Insert new pick
            new_pick = Pick(
                account_id=account_id,
                slot=slot,
                name_id=name_id,
                verdict=pick.verdict,
                decided_at=pick.decidedAt,
            )
            session.add(new_pick)

    session.commit()

    # A pick that loses a decidedAt comparison — or names a name the corpus does
    # not know — still counts as accepted: the client reads `accepted` as "how
    # many entries off the head of my outbox you took" (src/lib/syncQueue.ts
    # slices by it), so anything short of the whole batch would make it resend
    # picks the service already has, forever.
    accepted_count = len(request.picks)

    # Recompute swiper positions.
    #
    # A position is how far into served_order a swiper has gone, and it only
    # ever moves forward: POST /v1/deck/next advances it to the end of the block
    # it just handed out, and a flush can only confirm that the swiper reached at
    # least as far as the deepest name it decided. Taking the max of the two
    # keeps a partial flush from rewinding a swiper into cards it already saw.
    swipers_data: list[SwiperPosition] = []
    for slot in [0, 1]:
        # Get all name_ids this slot has picked
        picks_stmt = select(Pick.name_id).where(
            and_(Pick.account_id == account_id, Pick.slot == slot)
        )
        picked_name_ids: list[int] = [row[0] for row in session.execute(picks_stmt)]

        if picked_name_ids:
            # Find the max position from served_order for these names
            max_pos_stmt = (
                select(ServedOrder.position)
                .where(
                    and_(
                        ServedOrder.account_id == account_id,
                        ServedOrder.name_id.in_(picked_name_ids),
                    )
                )
                .order_by(ServedOrder.position.desc())
                .limit(1)
            )
            max_position = session.execute(max_pos_stmt).scalar_one_or_none()
            position = (max_position + 1) if max_position is not None else 0
        else:
            position = 0

        # Update the swiper's position
        swiper_stmt = select(Swiper).where(
            and_(Swiper.account_id == account_id, Swiper.slot == slot)
        )
        swiper = session.execute(swiper_stmt).scalar_one_or_none()
        if swiper:
            swiper.position = max(swiper.position, position)
            swipers_data.append(SwiperPosition(slot=slot, position=swiper.position))

    session.commit()

    return PicksResponse(accepted=accepted_count, swipers=swipers_data)
