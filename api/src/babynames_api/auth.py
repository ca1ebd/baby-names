import random
import uuid
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from babynames_api.config import settings
from babynames_api.db import get_session
from babynames_api.models.account import Account
from babynames_api.models.swiper import Swiper

security = HTTPBearer(auto_error=False)

_jwks_cache: dict[str, dict[str, Any]] | None = None


async def get_jwks() -> dict[str, dict[str, Any]]:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url, timeout=10.0)
        response.raise_for_status()
        jwks_data = response.json()

    _jwks_cache = {key["kid"]: key for key in jwks_data.get("keys", [])}
    return _jwks_cache


async def verify_token(token: str) -> str:
    """Verify JWT and return the sub claim"""
    try:
        # Decode header to get kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing kid in token header"
            )

        # Get JWKS
        jwks = await get_jwks()
        key = jwks.get(kid)

        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: unknown kid"
            )

        # Convert JWK dict to PyJWK object for jwt.decode
        jwk_obj = PyJWK.from_dict(key)

        # The signing algorithm comes from the JWK itself rather than being
        # hardcoded: Supabase projects created after its 2025 key rotation
        # sign with ES256 (elliptic curve), while the RS256 default only
        # matches older projects or this test suite's own JWKS fixture. A
        # hardcoded RS256 verifies fine against minted test tokens and rejects
        # every real one — this exact mismatch shipped a backend where no
        # authenticated endpoint ever worked, and only real end-to-end testing
        # against a live Supabase project surfaced it.
        payload = jwt.decode(
            token,
            jwk_obj.key,
            algorithms=[key.get("alg", "RS256")],
            audience=None,
            options={"verify_aud": False}
        )

        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing sub in token"
            )

        return sub

    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        ) from e


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: Annotated[Session, Depends(get_session)]
) -> uuid.UUID:
    """Verify JWT and provision account on first request"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    sub_str = await verify_token(credentials.credentials)
    account_id = uuid.UUID(sub_str)

    # Check if account exists
    stmt = select(Account).where(Account.id == account_id)
    account = session.scalar(stmt)

    if not account:
        # Provision a new account with two swipers and a deck seed.
        #
        # DO NOTHING rather than a plain insert: a client that boots and fires
        # its first few requests at once sends several unknown-sub requests
        # before any of them has committed, and the loser of that race should
        # join the account the winner created, not fail on a duplicate key.
        session.execute(
            pg_insert(Account)
            .values(
                id=account_id,
                deck_seed=random.randint(1, 2**31 - 1),
                last_name="",
                gender_filter="girl",
                onboarded=False,
            )
            .on_conflict_do_nothing(index_elements=[Account.id])
        )
        session.execute(
            pg_insert(Swiper)
            .values([
                {"account_id": account_id, "slot": slot, "label": "", "position": 0}
                for slot in (0, 1)
            ])
            .on_conflict_do_nothing(index_elements=[Swiper.account_id, Swiper.slot])
        )
        session.commit()

    return account_id
