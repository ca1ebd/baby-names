"""
T050: Contract test for POST /v1/deck/next.

The endpoint must:
- Return a block honoring the account's gender_filter
- Never repeat a name across calls (FR-015)
"""

from fastapi.testclient import TestClient


def test_deck_next_returns_block(client: TestClient, authed_headers: dict):
    """
    POST /v1/deck/next returns a block of names.
    """
    response = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 10},
        headers=authed_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert "block" in data
    assert "exhausted" in data
    assert isinstance(data["block"], list)
    assert isinstance(data["exhausted"], bool)
    assert len(data["block"]) <= 10


def test_deck_next_respects_gender_filter_girl(
    client: TestClient, authed_headers: dict, db_session
):
    """
    An account with genderFilter='girl' only receives girl names.
    """
    # The test account is created with genderFilter='girl' by default
    response = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 20},
        headers=authed_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # All names in the block should have gender='girl'
    for card in data["block"]:
        assert card["gender"] == "girl", f"Expected girl name, got {card}"


def test_deck_next_respects_gender_filter_boy(
    client: TestClient, db_session, auth_for_account
):
    """
    An account with genderFilter='boy' only receives boy names.
    """
    from babynames_api.models.account import Account

    # Create an account with boy filter
    account = Account(
        id="test-boy-account",
        deck_seed=12345,
        gender_filter="boy",
        onboarded=True,
    )
    db_session.add(account)
    db_session.commit()

    headers = auth_for_account(account.id)

    response = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 20},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    for card in data["block"]:
        assert card["gender"] == "boy", f"Expected boy name, got {card}"


def test_deck_next_never_repeats_names(client: TestClient, authed_headers: dict):
    """
    Calling /v1/deck/next multiple times never returns the same name twice (FR-015).
    """
    seen_names = set()

    # Request 5 blocks of 50 names each
    for _ in range(5):
        response = client.post(
            "/v1/deck/next",
            json={"slot": 0, "count": 50},
            headers=authed_headers,
        )

        assert response.status_code == 200
        data = response.json()

        for card in data["block"]:
            name = card["name"]
            assert name not in seen_names, f"Name '{name}' was dealt twice"
            seen_names.add(name)

    # Should have 250 unique names
    assert len(seen_names) == 250


def test_deck_next_clamps_count(client: TestClient, authed_headers: dict):
    """
    The count parameter is clamped to 1-200 per the contract.
    """
    # Request 0 names (clamped to 1)
    response = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 0},
        headers=authed_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["block"]) >= 1

    # Request 500 names (clamped to 200)
    response = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 500},
        headers=authed_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["block"]) <= 200


def test_deck_next_requires_auth(client: TestClient):
    """
    POST /v1/deck/next requires authentication.
    """
    response = client.post(
        "/v1/deck/next",
        json={"slot": 0, "count": 10},
    )
    assert response.status_code == 401
