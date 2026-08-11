import datetime
import uuid

import jwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from babynames_api.auth import verify_token


@pytest.fixture
def rsa_key_pair():
    """Generate RSA key pair for testing"""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )


@pytest.fixture
def mock_jwks(monkeypatch, rsa_key_pair):
    """Mock JWKS endpoint - return JWK dict format"""
    from jwt.algorithms import RSAAlgorithm

    public_key = rsa_key_pair.public_key()

    # Convert to JWK dict format
    jwk_dict = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk_dict["kid"] = "test-kid"
    jwk_dict["alg"] = "RS256"

    jwks = {
        "test-kid": jwk_dict
    }

    async def mock_get_jwks():
        return jwks

    import babynames_api.auth
    monkeypatch.setattr(babynames_api.auth, "get_jwks", mock_get_jwks)

    return rsa_key_pair


def create_token(private_key, sub: str, exp_delta: int = 3600, kid: str = "test-kid"):
    """Helper to create JWT"""
    now = datetime.datetime.now(tz=datetime.UTC)
    payload = {
        "sub": sub,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=exp_delta),
    }

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    return jwt.encode(
        payload,
        private_pem,
        algorithm="RS256",
        headers={"kid": kid}
    )


@pytest.mark.asyncio
async def test_valid_token_returns_sub(mock_jwks):
    """Valid JWT should return the sub claim"""
    sub = str(uuid.uuid4())
    token = create_token(mock_jwks, sub)

    result = await verify_token(token)

    assert result == sub


@pytest.mark.asyncio
async def test_expired_token_rejected(mock_jwks):
    """Expired JWT should raise 401"""
    sub = str(uuid.uuid4())
    token = create_token(mock_jwks, sub, exp_delta=-3600)

    with pytest.raises(Exception) as exc_info:
        await verify_token(token)

    assert exc_info.value.status_code == 401
    assert "expired" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_malformed_token_rejected():
    """Malformed JWT should raise 401"""
    with pytest.raises(Exception) as exc_info:
        await verify_token("not.a.valid.token")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_unsigned_token_rejected(mock_jwks):
    """Unsigned JWT should raise 401"""
    now = datetime.datetime.now(tz=datetime.UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "iat": now,
        "exp": now + datetime.timedelta(hours=1),
    }

    # Create token without signing
    token = jwt.encode(payload, "", algorithm="none")

    with pytest.raises(Exception) as exc_info:
        await verify_token(token)

    assert exc_info.value.status_code == 401
