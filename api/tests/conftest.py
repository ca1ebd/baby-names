import datetime
import uuid
from collections.abc import Generator

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from babynames_api.db import Base


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def test_engine(postgres_container):
    connection_url = postgres_container.get_connection_url(driver="psycopg")
    engine = create_engine(connection_url, pool_pre_ping=True)

    # Run migrations
    Base.metadata.create_all(bind=engine)

    yield engine

    engine.dispose()


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
