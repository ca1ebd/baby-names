"""
Deck algorithm: weighted shuffle for dealing names.

Ports the frontend's weightedShuffle faithfully, including the float64 underflow
that makes ~71% of the core sort by strict rank past position ~2,118.
"""

import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from babynames_api.models.account import Account
from babynames_api.models.name import Name
from babynames_api.models.served_order import ServedOrder
from babynames_api.models.swiper import Swiper


def lcg(seed: int) -> Callable[[], float]:
    """
    Linear congruential generator (LCG) - matches the frontend's rng(seed).

    Returns a function that generates the next pseudo-random number in [0, 1).
    Uses the same constants as the JavaScript version for identical output.
    """
    state = seed

    def next_random():
        nonlocal state
        state = (state * 1664525 + 1013904223) % 4294967296
        return state / 4294967296

    return next_random


def weighted_shuffle(items: list[str], seed: int) -> list[str]:
    """
    Weighted shuffle: each item gets key = u^(rank+1), sorted descending by key.

    This is a faithful port of the frontend's weightedShuffle, including the
    float64 underflow behavior where u^(rank+1) underflows to 0.0 starting
    around rank 230.

    Args:
        items: List of items to shuffle (in rank order, 0-indexed)
        seed: Random seed for reproducibility

    Returns:
        List of items in weighted-shuffled order
    """
    rng: Callable[[], float] = lcg(seed)

    # Assign keys: key = u^(rank+1) where u is random in [0,1)
    keyed_items: list[tuple[float, int, str]] = []
    for rank, item in enumerate(items):
        u: float = rng()
        # Float64 underflow: u^(rank+1) → 0.0 for large rank
        key: float = u ** (rank + 1)
        keyed_items.append((key, rank, item))

    # Sort by (key DESC, rank ASC) - stable sort preserves rank order for ties
    # When keys underflow to 0.0, rank becomes the tiebreaker
    keyed_items.sort(key=lambda x: (-x[0], x[1]))

    return [item for _, _, item in keyed_items]


def deal_block(
    db: Session,
    account_id: uuid.UUID,
    slot: int,
    count: int,
    gender_filter: str,
    deck_seed: int,
) -> tuple[list[dict[str, str | int]], bool]:
    """
    Deal the next block of names for a swiper, and advance that swiper past it.

    Returns names from the swiper's current position onward. If the requested
    run extends past the end of served_order, deals more names first by running
    the account-seeded weighted shuffle, skipping already-served names, and
    appending to served_order.

    Two calls racing on one account are serialized by a row lock on the account:
    served_order positions are dense and per-account, so two callers that both
    read "37 names served" would both try to write position 37. The lock is held
    until the single commit at the end, which is also what stops two calls from
    handing the same swiper the same block twice.

    Args:
        db: Database session
        account_id: Account ID
        slot: Swiper slot (0 or 1)
        count: Number of names requested (clamped to 1-200)
        gender_filter: 'girl', 'boy', or 'both'
        deck_seed: Account's deck seed

    Returns:
        Tuple of (block, exhausted) where:
        - block: List of dicts with {position, name, gender}
        - exhausted: True if the corpus is genuinely used up for this filter
    """
    # Clamp count to 1-200
    count = max(1, min(200, count))

    # Serialize dealing for this account. Everything below runs inside one
    # transaction, so the lock lives until the commit at the end.
    db.execute(select(Account.id).where(Account.id == account_id).with_for_update())

    # Get the swiper's current position
    swiper = db.query(Swiper).filter(
        Swiper.account_id == account_id,
        Swiper.slot == slot,
    ).first()

    if not swiper:
        raise ValueError(f"Swiper not found: account={account_id}, slot={slot}")

    start_position = swiper.position
    end_position = start_position + count

    # Get existing served_order entries for this account
    served_count = db.query(ServedOrder).filter(
        ServedOrder.account_id == account_id
    ).count()

    # If we need more names than we have served, deal more
    if end_position > served_count:
        # Get all names for the filter
        if gender_filter == "girl":
            corpus = db.query(Name).filter(Name.gender == "girl").order_by(Name.rank).all()
        elif gender_filter == "boy":
            corpus = db.query(Name).filter(Name.gender == "boy").order_by(Name.rank).all()
        else:  # "both"
            corpus = db.query(Name).order_by(Name.gender, Name.rank).all()

        # Convert to list of (id, name, gender, rank, is_core) tuples
        corpus_items = [(n.id, n.name, n.gender, n.rank, n.is_core) for n in corpus]

        # Separate core and tail based on is_core flag
        core_items = [item for item in corpus_items if item[4]]  # is_core
        tail_items = [item for item in corpus_items if not item[4]]

        # Weighted shuffle the core, flat shuffle the tail
        core_names = [item[1] for item in core_items]  # name strings
        core_shuffled_names = weighted_shuffle(core_names, deck_seed)

        tail_names = [item[1] for item in tail_items]
        tail_shuffled_names = flat_shuffle(tail_names, deck_seed + 1)

        # Combine into final order
        shuffled_names = core_shuffled_names + tail_shuffled_names

        # Build a name_id lookup
        name_to_id = {item[1]: (item[0], item[2]) for item in corpus_items}  # name -> (id, gender)

        # Get already-served name IDs for this account
        already_served = set(
            db.query(ServedOrder.name_id).filter(
                ServedOrder.account_id == account_id
            ).all()
        )
        already_served_ids = {row[0] for row in already_served}

        # Append to served_order, skipping already-served names
        new_entries: list[ServedOrder] = []
        for name in shuffled_names:
            name_id, _ = name_to_id.get(name, (None, None))
            if name_id and name_id not in already_served_ids:
                entry = ServedOrder(
                    account_id=account_id,
                    position=served_count + len(new_entries),
                    name_id=name_id,
                )
                new_entries.append(entry)
                already_served_ids.add(name_id)

                # Stop if we've dealt enough to satisfy the request
                if served_count + len(new_entries) >= end_position:
                    break

        db.bulk_save_objects(new_entries)
        db.flush()

        served_count += len(new_entries)

    # Now fetch the requested slice from served_order
    served_entries = (
        db.query(ServedOrder, Name)
        .join(Name, ServedOrder.name_id == Name.id)
        .filter(
            ServedOrder.account_id == account_id,
            ServedOrder.position >= start_position,
            ServedOrder.position < end_position,
        )
        .order_by(ServedOrder.position)
        .all()
    )

    block = [
        {
            "position": served.position,
            "name": name.name,
            "gender": name.gender,
        }
        for served, name in served_entries
    ]

    # Advance the swiper past the cards just handed out. Without this the next
    # call starts from the same position and deals the same block again, and the
    # trailing swiper never catches up to the leading one.
    if block:
        swiper.position = int(block[-1]["position"]) + 1

    db.commit()

    # Check if exhausted: block is shorter than requested
    exhausted = len(block) < count

    return block, exhausted


def flat_shuffle(items: list[str], seed: int) -> list[str]:
    """
    Fisher-Yates shuffle - matches the frontend's shuffled() function.

    Args:
        items: List of items to shuffle
        seed: Random seed for reproducibility

    Returns:
        Shuffled list
    """
    rng: Callable[[], float] = lcg(seed)
    result = items.copy()

    for k in range(len(result) - 1, 0, -1):
        j = int(rng() * (k + 1))
        result[k], result[j] = result[j], result[k]

    return result
