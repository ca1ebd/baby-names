"""Test GET /v1/state response structure"""
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


def test_state_returns_expected_structure(client_with_db, db_session):
    """GET /v1/state should return the account/swipers/picks shape from contracts"""
    from babynames_api.auth import get_current_user
    from babynames_api.models.account import Account
    from babynames_api.models.name import Name
    from babynames_api.models.pick import Pick
    from babynames_api.models.swiper import Swiper

    # Create account
    account_id = uuid.uuid4()
    account = Account(
        id=account_id,
        deck_seed=12345,
        last_name="TestName",
        gender_filter="girl",
        onboarded=True
    )
    db_session.add(account)

    # Add swipers
    swiper0 = Swiper(
        account_id=account_id,
        slot=0,
        label="Alex",
        position=5
    )
    swiper1 = Swiper(
        account_id=account_id,
        slot=1,
        label="Jordan",
        position=3
    )
    db_session.add(swiper0)
    db_session.add(swiper1)

    # Get existing name from corpus
    from sqlalchemy import select
    name = db_session.scalars(select(Name).limit(1)).first()
    if not name:
        name = Name(name="TestName1", gender="girl", rank=99999, is_core=False)
        db_session.add(name)
        db_session.flush()

    pick = Pick(
        account_id=account_id,
        slot=0,
        name_id=name.id,
        verdict="keep"
    )
    db_session.add(pick)
    db_session.commit()

    # Mock authentication
    def mock_get_current_user():
        return account_id

    app.dependency_overrides[get_current_user] = mock_get_current_user

    try:
        response = client_with_db.get("/v1/state")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "account" in data
        assert "swipers" in data
        assert "picks" in data

        # Check account shape
        account_data = data["account"]
        assert account_data["lastName"] == "TestName"
        assert account_data["genderFilter"] == "girl"
        assert account_data["onboarded"] is True

        # Check swipers shape (should be list of 2)
        assert len(data["swipers"]) == 2
        swiper_data = data["swipers"][0]
        assert "slot" in swiper_data
        assert "label" in swiper_data
        assert "position" in swiper_data

        # Check picks shape
        assert len(data["picks"]) > 0
        pick_data = data["picks"][0]
        assert "slot" in pick_data
        assert "name" in pick_data
        assert "verdict" in pick_data
    finally:
        del app.dependency_overrides[get_current_user]
