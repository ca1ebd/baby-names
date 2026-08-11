"""
T051: Integration test for per-account deck seeds.

Two accounts with the same gender_filter get visibly different orders,
and each account's own order is reproducible across repeated runs (SC-004).
"""

from fastapi.testclient import TestClient


def test_different_accounts_get_different_orders(
    client: TestClient, db_session, make_account
):
    """
    Two accounts with the same genderFilter receive different deck orders.
    """
    # Same filter, different seeds — the seed is the only thing that differs
    _, headers1 = make_account(deck_seed=11111, gender_filter="girl")
    _, headers2 = make_account(deck_seed=22222, gender_filter="girl")

    # Get first block for each account
    response1 = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 20},
        headers=headers1,
    )
    response2 = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 20},
        headers=headers2,
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    block1 = [card["name"] for card in response1.json()["block"]]
    block2 = [card["name"] for card in response2.json()["block"]]

    # The orders should be visibly different
    assert block1 != block2, "Two accounts should have different deck orders"


def test_account_order_is_reproducible(client: TestClient, db_session, make_account):
    """
    An account's deck order is reproducible across repeated runs (SC-004).
    """
    from babynames_api.models.swiper import Swiper

    account, headers = make_account(deck_seed=55555, gender_filter="girl")

    # Get first 50 names
    response1 = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 50},
        headers=headers,
    )
    assert response1.status_code == 200
    first_run = [card["name"] for card in response1.json()["block"]]

    # Get next 50 names
    response2 = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 50},
        headers=headers,
    )
    assert response2.status_code == 200
    second_run = [card["name"] for card in response2.json()["block"]]

    # Now rewind the swiper and ask for the same span in one request. The
    # already-dealt order is frozen in served_order, so it must replay exactly.
    swiper0 = (
        db_session.query(Swiper)
        .filter(Swiper.account_id == account.id, Swiper.slot == 0)
        .one()
    )
    swiper0.position = 0
    db_session.commit()

    response3 = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 100},
        headers=headers,
    )
    assert response3.status_code == 200
    full_run = [card["name"] for card in response3.json()["block"]]

    # The full run should match the concatenation of first + second
    assert full_run == first_run + second_run, (
        "Deck order should be reproducible regardless of block size"
    )
