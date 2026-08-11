"""
T052: Integration test for shared deck order.

Both swipers on one account, and the same account on a second device,
are dealt the identical order (US2 scenario 5).
"""

from fastapi.testclient import TestClient


def test_both_swipers_see_same_deck_order(client: TestClient, db_session, make_account):
    """
    Both swipers on one account are dealt the identical order.
    """
    _, headers = make_account(deck_seed=99999, gender_filter="girl")

    # Get first 30 cards for swiper 0
    response0 = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 30},
        headers=headers,
    )
    assert response0.status_code == 200
    block0 = [card["name"] for card in response0.json()["block"]]

    # Get first 30 cards for swiper 1
    response1 = client.post(
        "/v1/deck/next",
        json={"slot": 1, "count": 30},
        headers=headers,
    )
    assert response1.status_code == 200
    block1 = [card["name"] for card in response1.json()["block"]]

    # Both swipers should see identical order
    assert block0 == block1, (
        "Both swipers on the same account should see the same deck order"
    )


def test_trailing_swiper_sees_same_cards(client: TestClient, db_session, make_account):
    """
    The trailing swiper sees the exact same cards the leading swiper saw.
    """
    from babynames_api.models.swiper import Swiper

    account, headers = make_account(deck_seed=77777, gender_filter="boy")

    # Swiper 0 gets first 100 cards
    response0_a = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 100},
        headers=headers,
    )
    assert response0_a.status_code == 200
    leader_first_100 = [card["name"] for card in response0_a.json()["block"]]

    # Update swiper 0's position
    swiper0 = (
        db_session.query(Swiper)
        .filter(Swiper.account_id == account.id, Swiper.slot == 0)
        .one()
    )
    db_session.refresh(swiper0)
    assert swiper0.position == 100

    # Swiper 0 gets next 50 cards
    response0_b = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 50},
        headers=headers,
    )
    assert response0_b.status_code == 200
    leader_next_50 = [card["name"] for card in response0_b.json()["block"]]

    # Now swiper 1 (still at position 0) gets first 150 cards
    response1 = client.post(
        "/v1/deck/next",
        json={"slot": 1, "count": 150},
        headers=headers,
    )
    assert response1.status_code == 200
    trailer_first_150 = [card["name"] for card in response1.json()["block"]]

    # The trailer's 150 cards should exactly match the leader's 100 + 50
    assert trailer_first_150 == leader_first_100 + leader_next_50, (
        "Trailing swiper should see the exact same cards in the exact same order"
    )
