"""Test state endpoint authentication and authorization"""
import uuid

import pytest
from fastapi.testclient import TestClient

from babynames_api.db import get_session
from babynames_api.main import app


@pytest.fixture
def client_with_db(db_session):
    """TestClient with working database"""
    def get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = get_test_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_state_without_token_returns_401(client_with_db):
    """GET /v1/state without authorization should return 401"""
    response = client_with_db.get("/v1/state")

    assert response.status_code == 401
    assert "error" in response.json()


def test_state_with_invalid_token_returns_401(client_with_db):
    """GET /v1/state with invalid token should return 401"""
    response = client_with_db.get(
        "/v1/state",
        headers={"Authorization": "Bearer invalid.token.here"}
    )

    assert response.status_code == 401
    assert "error" in response.json()


def test_state_returns_only_own_account_data(client_with_db, db_session):
    """GET /v1/state should return only the authenticated account's data (SC-006)"""
    from babynames_api.auth import get_current_user
    from babynames_api.models.account import Account
    from babynames_api.models.swiper import Swiper

    # Create two accounts
    account1_id = uuid.uuid4()
    account2_id = uuid.uuid4()

    account1 = Account(
        id=account1_id,
        deck_seed=12345,
        last_name="Smith",
        gender_filter="girl",
        onboarded=True
    )
    account2 = Account(
        id=account2_id,
        deck_seed=67890,
        last_name="Jones",
        gender_filter="boy",
        onboarded=True
    )

    db_session.add(account1)
    db_session.add(account2)

    # Add swipers for account1
    for slot in [0, 1]:
        db_session.add(Swiper(
            account_id=account1_id,
            slot=slot,
            label=f"Person{slot+1}",
            position=0
        ))

    db_session.commit()

    # Mock authentication to return account1_id
    def mock_get_current_user():
        return account1_id

    app.dependency_overrides[get_current_user] = mock_get_current_user

    try:
        response = client_with_db.get("/v1/state")

        assert response.status_code == 200
        data = response.json()

        # Should only see account1's data
        assert data["account"]["lastName"] == "Smith"
        assert data["account"]["genderFilter"] == "girl"

        # Should NOT see account2's data
        assert data["account"]["lastName"] != "Jones"
    finally:
        del app.dependency_overrides[get_current_user]
