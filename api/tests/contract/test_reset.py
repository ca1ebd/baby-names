"""Test POST /v1/reset endpoint"""
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


def test_reset_everything_clears_all_data(client_with_db, db_session):
    """
    POST /v1/reset with scope=everything should clear picks,
    served_order, positions, set onboarded=false
    """
    from babynames_api.models.account import Account
    from babynames_api.models.name import Name
    from babynames_api.models.pick import Pick
    from babynames_api.models.served_order import ServedOrder
    from babynames_api.models.swiper import Swiper

    # Create account with data
    account_id = uuid.uuid4()
    account = Account(
        id=account_id,
        deck_seed=12345,
        last_name="Test",
        gender_filter="girl",
        onboarded=True
    )
    db_session.add(account)

    swipers = [
        Swiper(account_id=account_id, slot=0, label="A", position=10),
        Swiper(account_id=account_id, slot=1, label="B", position=5)
    ]
    for s in swipers:
        db_session.add(s)

    # Get existing name from corpus instead of creating
    from sqlalchemy import select
    name = db_session.scalars(select(Name).limit(1)).first()
    if not name:
        name = Name(name="TestName1", gender="girl", rank=99999, is_core=False)
        db_session.add(name)
        db_session.flush()

    pick = Pick(account_id=account_id, slot=0, name_id=name.id, verdict="keep")
    served = ServedOrder(account_id=account_id, position=0, name_id=name.id)
    db_session.add(pick)
    db_session.add(served)
    db_session.commit()

    # Mock auth
    app.dependency_overrides[get_current_user] = lambda: account_id

    try:
        response = client_with_db.post("/v1/reset", json={"scope": "everything"})
        assert response.status_code == 200

        # Verify all cleared
        db_session.expire_all()
        updated_account = db_session.get(Account, account_id)
        assert updated_account.onboarded is False

        picks_count = db_session.query(Pick).filter_by(account_id=account_id).count()
        served_count = db_session.query(ServedOrder).filter_by(account_id=account_id).count()
        assert picks_count == 0
        assert served_count == 0

        updated_swipers = db_session.query(Swiper).filter_by(account_id=account_id).all()
        for swiper in updated_swipers:
            assert swiper.position == 0
    finally:
        del app.dependency_overrides[get_current_user]


def test_reset_swiper_clears_only_that_slot(client_with_db, db_session):
    """POST /v1/reset with scope=swiper should clear only that swiper's picks"""
    from babynames_api.models.account import Account
    from babynames_api.models.name import Name
    from babynames_api.models.pick import Pick
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
        db_session.add(Swiper(account_id=account_id, slot=slot, label=f"P{slot}", position=5))

    # Get existing name from corpus instead of creating
    from sqlalchemy import select
    name = db_session.scalars(select(Name).limit(1)).first()
    if not name:
        name = Name(name="TestName1", gender="girl", rank=99999, is_core=False)
        db_session.add(name)
        db_session.flush()

    # Add picks for both slots
    pick0 = Pick(account_id=account_id, slot=0, name_id=name.id, verdict="keep")
    pick1 = Pick(account_id=account_id, slot=1, name_id=name.id, verdict="no")
    db_session.add(pick0)
    db_session.add(pick1)
    db_session.commit()

    # Mock auth
    app.dependency_overrides[get_current_user] = lambda: account_id

    try:
        response = client_with_db.post("/v1/reset", json={"scope": "swiper", "slot": 0})
        assert response.status_code == 200

        # Verify only slot 0 cleared
        db_session.expire_all()
        picks = db_session.query(Pick).filter_by(account_id=account_id).all()
        assert len(picks) == 1
        assert picks[0].slot == 1  # slot 1 pick remains

        swiper0 = db_session.query(Swiper).filter_by(account_id=account_id, slot=0).first()
        swiper1 = db_session.query(Swiper).filter_by(account_id=account_id, slot=1).first()
        assert swiper0.position == 0  # Reset
        assert swiper1.position == 5  # Unchanged
    finally:
        del app.dependency_overrides[get_current_user]
