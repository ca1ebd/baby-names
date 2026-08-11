"""Test state restore on fresh session (SC-001)"""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from babynames_api.auth import get_current_user
from babynames_api.db import get_session
from babynames_api.main import app
from babynames_api.models.account import Account
from babynames_api.models.name import Name
from babynames_api.models.pick import Pick
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


def test_fresh_session_restores_100_percent_of_state(
    client_with_db, db_session, corpus_names
):
    """
    Signing in from fresh session should restore 100% of picks, matches,
    labels, last name, gender filter (SC-001)
    """
    # Create account with complete state
    account_id = uuid.uuid4()
    account = Account(
        id=account_id,
        deck_seed=12345,
        last_name="TestFamily",
        gender_filter="boy",
        onboarded=True
    )
    db_session.add(account)

    # Add swipers with labels and positions
    swiper0 = Swiper(
        account_id=account_id,
        slot=0,
        label="Alice",
        position=10
    )
    swiper1 = Swiper(
        account_id=account_id,
        slot=1,
        label="Bob",
        position=5
    )
    db_session.add(swiper0)
    db_session.add(swiper1)

    # Pick five names out of the seeded corpus. Picks reference names by id, so
    # they have to be names the service already knows.
    names = [
        db_session.scalars(select(Name).where(Name.name == name_str)).one()
        for name_str in corpus_names[:5]
    ]

    # Add picks for both swipers
    picks_data = [
        (0, names[0].id, "keep"),
        (0, names[1].id, "no"),
        (0, names[2].id, "keep"),  # Match
        (1, names[2].id, "keep"),  # Match
        (1, names[3].id, "no"),
        (1, names[4].id, "keep"),
    ]

    decided_at = datetime.datetime(2026, 8, 9, 18, 4, 11, tzinfo=datetime.UTC)
    for slot, name_id, verdict in picks_data:
        pick = Pick(
            account_id=account_id,
            slot=slot,
            name_id=name_id,
            verdict=verdict,
            decided_at=decided_at
        )
        db_session.add(pick)

    db_session.commit()

    # Mock auth
    app.dependency_overrides[get_current_user] = lambda: account_id

    try:
        # Simulate fresh session by getting state
        response = client_with_db.get("/v1/state")
        assert response.status_code == 200

        data = response.json()

        # Verify account data restored
        assert data["account"]["lastName"] == "TestFamily"
        assert data["account"]["genderFilter"] == "boy"
        assert data["account"]["onboarded"] is True

        # Verify swiper labels and positions restored
        swipers_by_slot = {s["slot"]: s for s in data["swipers"]}
        assert swipers_by_slot[0]["label"] == "Alice"
        assert swipers_by_slot[0]["position"] == 10
        assert swipers_by_slot[1]["label"] == "Bob"
        assert swipers_by_slot[1]["position"] == 5

        # Verify all picks restored
        assert len(data["picks"]) == 6

        # Verify picks have correct structure
        picks_by_name = {p["name"]: p for p in data["picks"]}
        assert names[0].name in picks_by_name
        assert names[1].name in picks_by_name

        # Count matches (both said yes)
        keeps_by_name = {}
        for pick in data["picks"]:
            if pick["verdict"] == "keep":
                keeps_by_name[pick["name"]] = keeps_by_name.get(pick["name"], 0) + 1

        # names[2] should be a match (both kept it)
        matches = [name for name, count in keeps_by_name.items() if count == 2]
        assert len(matches) >= 1
        assert names[2].name in matches
    finally:
        del app.dependency_overrides[get_current_user]
