"""
T051: Integration test for per-account deck seeds.

Two accounts with the same gender_filter get visibly different orders,
and each account's own order is reproducible across repeated runs (SC-004).
"""

from fastapi.testclient import TestClient


def test_different_accounts_get_different_orders(
    client: TestClient, db_session, auth_for_account
):
    """
    Two accounts with the same genderFilter receive different deck orders.
    """
    from babynames_api.models.account import Account

    # Create two accounts with different seeds but same filter
    account1 = Account(
        id="account-1",
        deck_seed=11111,
        gender_filter="girl",
        onboarded=True,
    )
    account2 = Account(
        id="account-2",
        deck_seed=22222,
        gender_filter="girl",
        onboarded=True,
    )
    db_session.add_all([account1, account2])
    db_session.commit()

    headers1 = auth_for_account(account1.id)
    headers2 = auth_for_account(account2.id)

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


def test_account_order_is_reproducible(
    client: TestClient, db_session, auth_for_account
):
    """
    An account's deck order is reproducible across repeated runs (SC-004).
    """
    from babynames_api.models.account import Account
    from babynames_api.models.swiper import Swiper

    # Create account
    account = Account(
        id="reproducible-account",
        deck_seed=55555,
        gender_filter="girl",
        onboarded=True,
    )
    db_session.add(account)
    db_session.commit()

    # Add swipers
    swiper0 = Swiper(account_id=account.id, slot=0, label="Test", position=0)
    db_session.add(swiper0)
    db_session.commit()

    headers = auth_for_account(account.id)

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

    # Now reset the swiper position and get first 100 again
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
