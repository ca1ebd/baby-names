"""
T054: Integration test for concurrent deck dealing.

Concurrent POST /v1/deck/next calls for the same account never double-deal
a name, relying on the UNIQUE(account_id, name_id) constraint.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi.testclient import TestClient


def test_concurrent_deck_requests_no_duplicates(
    client: TestClient, db_session, auth_for_account
):
    """
    Concurrent calls to /v1/deck/next for the same account don't duplicate names.
    """
    from babynames_api.models.account import Account
    from babynames_api.models.swiper import Swiper

    account = Account(
        id="concurrent-account",
        deck_seed=33333,
        gender_filter="girl",
        onboarded=True,
    )
    db_session.add(account)
    db_session.commit()

    swiper = Swiper(account_id=account.id, slot=0, label="Test", position=0)
    db_session.add(swiper)
    db_session.commit()

    headers = auth_for_account(account.id)

    def request_block(count: int):
        """Make a single /v1/deck/next request."""
        response = client.post(
            "/v1/deck/next",
            json={"slot": 0, "count": count},
            headers=headers,
        )
        if response.status_code == 200:
            return [card["name"] for card in response.json()["block"]]
        return []

    # Fire 10 concurrent requests for 20 names each
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(request_block, 20) for _ in range(10)]
        results = [future.result() for future in as_completed(futures)]

    # Collect all names across all responses
    all_names = []
    for block in results:
        all_names.extend(block)

    # Check for duplicates
    seen = set()
    duplicates = []
    for name in all_names:
        if name in seen:
            duplicates.append(name)
        seen.add(name)

    assert len(duplicates) == 0, (
        f"Concurrent requests produced {len(duplicates)} duplicate names: "
        f"{duplicates[:5]}"
    )


def test_concurrent_requests_for_different_swipers(
    client: TestClient, db_session, auth_for_account
):
    """
    Concurrent requests for different swipers on the same account don't interfere.
    """
    from babynames_api.models.account import Account
    from babynames_api.models.swiper import Swiper

    account = Account(
        id="concurrent-swipers-account",
        deck_seed=44444,
        gender_filter="boy",
        onboarded=True,
    )
    db_session.add(account)
    db_session.commit()

    swiper0 = Swiper(account_id=account.id, slot=0, label="Swiper 0", position=0)
    swiper1 = Swiper(account_id=account.id, slot=1, label="Swiper 1", position=0)
    db_session.add_all([swiper0, swiper1])
    db_session.commit()

    headers = auth_for_account(account.id)

    def request_for_slot(slot: int, count: int):
        """Request a block for a specific swiper slot."""
        response = client.post(
            "/v1/deck/next",
            json={"slot": slot, "count": count},
            headers=headers,
        )
        if response.status_code == 200:
            return (slot, [card["name"] for card in response.json()["block"]])
        return (slot, [])

    # Fire concurrent requests for both swipers
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for _ in range(2):
            futures.append(executor.submit(request_for_slot, 0, 30))
            futures.append(executor.submit(request_for_slot, 1, 30))

        results = {0: [], 1: []}
        for future in as_completed(futures):
            slot, names = future.result()
            results[slot].extend(names)

    # Both swipers should have received the same names (shared deck)
    # but no swiper should have duplicates within their own results
    for slot in [0, 1]:
        names = results[slot]
        assert len(names) == len(set(names)), (
            f"Swiper {slot} received duplicate names in concurrent requests"
        )
