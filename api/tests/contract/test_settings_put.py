"""Test PUT /v1/settings endpoint"""
import uuid

import pytest
from fastapi.testclient import TestClient

from babynames_api.auth import get_current_user
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


def test_settings_updates_account_and_swipers(client_with_db, db_session):
    """PUT /v1/settings should update account and swiper labels"""
    from babynames_api.models.account import Account
    from babynames_api.models.swiper import Swiper

    # Create account
    account_id = uuid.uuid4()
    account = Account(
        id=account_id,
        deck_seed=12345,
        last_name="OldName",
        gender_filter="girl",
        onboarded=False
    )
    db_session.add(account)

    # Add swipers
    for slot in [0, 1]:
        db_session.add(Swiper(
            account_id=account_id,
            slot=slot,
            label=f"Old{slot}",
            position=0
        ))
    db_session.commit()

    # Mock auth
    def mock_auth():
        return account_id
    app.dependency_overrides[get_current_user] = mock_auth

    try:
        response = client_with_db.put("/v1/settings", json={
            "lastName": "NewName",
            "genderFilter": "boy",
            "onboarded": True,
            "swiper0Label": "Alice",
            "swiper1Label": "Bob"
        })

        assert response.status_code == 200

        # Verify updates
        db_session.expire_all()
        updated_account = db_session.get(Account, account_id)
        assert updated_account.last_name == "NewName"
        assert updated_account.gender_filter == "boy"
        assert updated_account.onboarded is True

        swipers = (
            db_session.query(Swiper)
            .filter_by(account_id=account_id)
            .order_by(Swiper.slot)
            .all()
        )
        assert swipers[0].label == "Alice"
        assert swipers[1].label == "Bob"
    finally:
        del app.dependency_overrides[get_current_user]


def test_settings_leaves_served_order_untouched(client_with_db, db_session):
    """PUT /v1/settings with genderFilter change should not affect served_order"""
    from babynames_api.models.account import Account
    from babynames_api.models.name import Name
    from babynames_api.models.served_order import ServedOrder
    from babynames_api.models.swiper import Swiper

    # Create account
    account_id = uuid.uuid4()
    account = Account(
        id=account_id,
        deck_seed=12345,
        last_name="Test",
        gender_filter="girl",
        onboarded=True
    )
    db_session.add(account)

    for slot in [0, 1]:
        db_session.add(Swiper(account_id=account_id, slot=slot, label=f"P{slot}", position=0))

    # Get existing name from corpus
    from sqlalchemy import select
    name = db_session.scalars(select(Name).limit(1)).first()
    if not name:
        name = Name(name="TestName1", gender="girl", rank=99999, is_core=False)
        db_session.add(name)
        db_session.flush()

    served = ServedOrder(account_id=account_id, position=0, name_id=name.id)
    db_session.add(served)
    db_session.commit()

    # Mock auth
    app.dependency_overrides[get_current_user] = lambda: account_id

    try:
        response = client_with_db.put("/v1/settings", json={
            "lastName": "Test",
            "genderFilter": "boy",  # Changed
            "onboarded": True,
            "swiper0Label": "P0",
            "swiper1Label": "P1"
        })

        assert response.status_code == 200

        # Verify served_order unchanged
        db_session.expire_all()
        served_count = db_session.query(ServedOrder).filter_by(account_id=account_id).count()
        assert served_count == 1
    finally:
        del app.dependency_overrides[get_current_user]
