"""State endpoint - returns full account state"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from babynames_api.auth import get_current_user
from babynames_api.db import get_session
from babynames_api.ratelimit import check_rate_limit
from babynames_api.schemas.state import StateResponse
from babynames_api.state import load_state

router = APIRouter(prefix="/v1", tags=["state"])


@router.get("/state")
def get_state(
    account_id: Annotated[uuid.UUID, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    _rate_limit: Annotated[None, Depends(check_rate_limit)],
) -> StateResponse:
    """Get full account state - account, swipers, and picks"""
    return load_state(session, account_id)
