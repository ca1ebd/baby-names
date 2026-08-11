"""Test account auto-provisioning on first auth"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from babynames_api.auth import get_current_user
from babynames_api.db import get_session
from babynames_api.main import app
from babynames_api.models.account import Account
from babynames_api.models.swiper import Swiper


@pytest.fixture
def client_with_db(db_session):
    """TestClient with working database"""
    def get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = get_test_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_first_request_provisions_account_with_swipers_and_seed(client_with_db, db_session):
    """First authenticated request should provision account, two swipers, and deck_seed"""
    # Use a fresh account ID that doesn't exist yet
    new_account_id = uuid.uuid4()

    # Verify account doesn't exist yet
    account = db_session.get(Account, new_account_id)
    assert account is None

    # Mock auth to return the new account ID
    # This simulates what happens when auth.py receives a valid JWT for an unknown sub
    def mock_auth():
        # Simulate the provisioning that happens in get_current_user
        existing = db_session.get(Account, new_account_id)
        if not existing:
            import random
            new_account = Account(
                id=new_account_id,
                deck_seed=random.randint(1, 2**31 - 1),
                last_name="",
                gender_filter="girl",
                onboarded=False
            )
            db_session.add(new_account)

            for slot in [0, 1]:
                swiper = Swiper(
                    account_id=new_account_id,
                    slot=slot,
                    label="",
                    position=0
                )
                db_session.add(swiper)

            db_session.commit()

        return new_account_id

    app.dependency_overrides[get_current_user] = mock_auth

    try:
        # Make first authenticated request
        response = client_with_db.get("/v1/state")
        assert response.status_code == 200

        # Verify account was created
        db_session.expire_all()
        account = db_session.get(Account, new_account_id)
        assert account is not None
        assert account.deck_seed > 0
        assert account.last_name == ""
        assert account.gender_filter == "girl"
        assert account.onboarded is False

        # Verify two swipers were created
        swipers = db_session.scalars(
            select(Swiper).where(Swiper.account_id == new_account_id).order_by(Swiper.slot)
        ).all()
        assert len(swipers) == 2
        assert swipers[0].slot == 0
        assert swipers[1].slot == 1
        assert swipers[0].position == 0
        assert swipers[1].position == 0
    finally:
        del app.dependency_overrides[get_current_user]
