from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from babynames_api.db import get_session

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check(session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
    """Health check endpoint - tests database connectivity"""
    try:
        session.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="ok")
    except Exception:
        return HealthResponse(status="degraded", database="error")
