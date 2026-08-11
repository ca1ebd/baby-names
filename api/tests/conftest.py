import datetime
import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from babynames_api.db import Base
from babynames_api.main import create_app
from babynames_api.models.account import Account
from babynames_api.models.name import Name
from babynames_api.models.swiper import Swiper


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


# A stand-in corpus, deliberately tiny: the real one is 63,880 names, and tests
# that walk a filter to exhaustion have to be able to reach the end in a few
# requests. Big enough that the 250-name no-repeat contract test still fits.
CORPUS_SIZE = 300
CORPUS_CORE_SIZE = 100
GIRL_NAMES = [f"Girl{i:03d}" for i in range(CORPUS_SIZE)]
BOY_NAMES = [f"Boy{i:03d}" for i in range(CORPUS_SIZE)]


@pytest.fixture(scope="session")
def test_engine(postgres_container):
    connection_url = postgres_container.get_connection_url(driver="psycopg")
    engine = create_engine(connection_url, pool_pre_ping=True)

    # Run migrations
    Base.metadata.create_all(bind=engine)

    # Seed the stand-in corpus. Picks reference names by id, so anything a test
    # wants to swipe has to exist here first — see the `corpus_names` fixture.
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_local()
    try:
        for rank, name in enumerate(GIRL_NAMES):
            is_core = rank < CORPUS_CORE_SIZE
            session.add(Name(name=name, gender="girl", rank=rank, is_core=is_core))

        for rank, name in enumerate(BOY_NAMES):
            is_core = rank < CORPUS_CORE_SIZE
            session.add(Name(name=name, gender="boy", rank=rank, is_core=is_core))

        session.commit()
    finally:
        session.close()

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def corpus_names() -> list[str]:
    """
    The seeded girl names, in rank order.

    Tests that flush picks draw their names from here. A pick for a name outside
    the corpus is dropped by design (the service owns the name list, FR-012), so
    inventing name strings in a test would silently assert nothing.
    """
    return list(GIRL_NAMES)


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = session_local()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def jwks_test_key():
    """Test RSA key pair for JWT signing/verification"""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    return {
        "private_key": private_key,
        "kid": "test-key-1",
        "alg": "RS256"
    }


@pytest.fixture(scope="function")
def mint_jwt(jwks_test_key):
    """Factory fixture to create test JWTs"""
    def _mint(sub: str | None = None, exp_delta: int = 3600, **claims):
        if sub is None:
            sub = str(uuid.uuid4())

        now = datetime.datetime.now(tz=datetime.UTC)
        payload = {
            "sub": sub,
            "iat": now,
            "exp": now + datetime.timedelta(seconds=exp_delta),
            **claims
        }

        from cryptography.hazmat.primitives import serialization

        private_pem = jwks_test_key["private_key"].private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        token = jwt.encode(
            payload,
            private_pem,
            algorithm=jwks_test_key["alg"],
            headers={"kid": jwks_test_key["kid"]}
        )

        return token, sub

    return _mint


@pytest.fixture(scope="function")
def client(test_engine, jwks_test_key):
    """FastAPI TestClient with database session override and mocked JWKS"""
    from jwt.algorithms import RSAAlgorithm

    from babynames_api import auth
    from babynames_api.db import get_session

    # Create JWK dict from test key using PyJWT's RSA algorithm
    public_key = jwks_test_key["private_key"].public_key()
    jwk_dict = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk_dict["kid"] = jwks_test_key["kid"]
    jwk_dict["alg"] = jwks_test_key["alg"]

    # Mock JWKS cache with the properly formatted JWK dict
    jwks_dict: dict[str, dict[str, Any]] = {
        jwks_test_key["kid"]: jwk_dict
    }

    # One session per request, exactly as db.get_session does in production.
    # Handing every request the test's own session instead would make the
    # concurrent-deal tests collide inside SQLAlchemy rather than in Postgres,
    # which is the layer they exist to exercise.
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def request_session() -> Generator[Session, None, None]:
        session = session_local()
        try:
            yield session
        finally:
            session.close()

    with patch.object(auth, '_jwks_cache', jwks_dict):
        app = create_app()

        # Override the get_session dependency
        app.dependency_overrides[get_session] = request_session

        with TestClient(app) as test_client:
            yield test_client

        app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_account(db_session, mint_jwt):
    """Create a test account with swipers"""
    token, account_id = mint_jwt()

    # Create account
    account = Account(
        id=uuid.UUID(account_id),
        deck_seed=12345,
        last_name="Test",
        gender_filter="girl",
        onboarded=True
    )
    db_session.add(account)

    # Create swipers
    for slot in [0, 1]:
        swiper = Swiper(
            account_id=account.id,
            slot=slot,
            label=f"Swiper{slot}",
            position=0
        )
        db_session.add(swiper)

    db_session.commit()

    yield account, account_id, token


@pytest.fixture(scope="function")
def auth_headers(test_account):
    """Auth headers with valid JWT"""
    _, _, token = test_account
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def authed_headers(auth_headers):
    """Alias for auth_headers"""
    return auth_headers


@pytest.fixture(scope="function")
def auth_for_account(mint_jwt):
    """Factory fixture to create auth headers for a specific account ID"""
    def _auth_for(account_id: str | uuid.UUID) -> dict[str, str]:
        if isinstance(account_id, uuid.UUID):
            account_id = str(account_id)
        token, _ = mint_jwt(sub=account_id)
        return {"Authorization": f"Bearer {token}"}

    return _auth_for


@pytest.fixture(scope="function")
def make_account(db_session, auth_for_account):
    """
    Factory: create an account with its two swipers and return it with auth headers.

    The account id *is* the Supabase `sub` (data-model.md), so it has to be a
    real UUID — a readable placeholder like "exhaustion-account" never reaches
    the endpoint, it just fails in the uuid column.
    """
    def _make(
        *,
        deck_seed: int,
        gender_filter: str = "girl",
        slots: tuple[int, ...] = (0, 1),
        last_name: str = "",
    ) -> tuple[Account, dict[str, str]]:
        account = Account(
            id=uuid.uuid4(),
            deck_seed=deck_seed,
            last_name=last_name,
            gender_filter=gender_filter,
            onboarded=True,
        )
        db_session.add(account)
        db_session.flush()

        for slot in slots:
            db_session.add(
                Swiper(
                    account_id=account.id,
                    slot=slot,
                    label=f"Swiper{slot}",
                    position=0,
                )
            )

        db_session.commit()
        return account, auth_for_account(account.id)

    return _make


@pytest.fixture(scope="function")
def name_ids(db_session):
    """Create some test names and return their IDs"""
    from sqlalchemy import select

    # Use high ranks to avoid conflicts with the test corpus (which uses 0-199)
    names_data = [
        ("Emma", "girl", 1000, True),
        ("Olivia", "girl", 1001, True),
        ("Ava", "girl", 1002, True),
        ("Sophia", "girl", 1003, True),
        ("Isabella", "girl", 1004, True),
        ("Mia", "girl", 1005, True),
        ("Charlotte", "girl", 1006, True),
        ("Amelia", "girl", 1007, True),
        ("Nora", "girl", 1008, True),
        ("Wren", "girl", 1009, True),
    ]

    name_id_map = {}
    for name_str, gender, rank, is_core in names_data:
        # Check if name already exists
        existing = db_session.execute(
            select(Name).where(Name.name == name_str)
        ).scalar_one_or_none()

        if existing:
            name_id_map[name_str] = existing.id
        else:
            name = Name(
                name=name_str,
                gender=gender,
                rank=rank,
                is_core=is_core
            )
            db_session.add(name)
            db_session.flush()
            name_id_map[name_str] = name.id

    db_session.commit()

    return name_id_map
