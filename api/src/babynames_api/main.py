from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from babynames_api.config import settings
from babynames_api.errors import error_code_for_status
from babynames_api.routers import deck, health, picks, reset, state
from babynames_api.routers import settings as settings_router


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def _first_validation_message(exc: RequestValidationError) -> str:
    """One human-readable line for the first thing wrong with the request body."""
    errors = exc.errors()
    if not errors:
        return "Invalid request"

    first = errors[0]
    location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    message = first.get("msg", "Invalid request")
    return f"{location}: {message}" if location else message


def create_app() -> FastAPI:
    app = FastAPI(title="Baby Names API", version="0.1.0")

    # CORS
    origins = [origin.strip() for origin in settings.cors_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handling
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[reportUnusedFunction]
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=error_code_for_status(exc, exc.status_code),
                    message=exc.detail
                )
            ).model_dump(),
            headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(  # type: ignore[reportUnusedFunction]
        request: Request, exc: RequestValidationError
    ):
        # A malformed body is a client bug, not a 422 the client can act on —
        # collapse FastAPI's default shape into the contract's error envelope so
        # every failure the client sees has the same three fields.
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="invalid_request",
                    message=_first_validation_message(exc)
                )
            ).model_dump()
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):  # type: ignore[reportUnusedFunction]
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="500",
                    message="Internal server error"
                )
            ).model_dump()
        )

    # Routers
    app.include_router(health.router, tags=["health"])
    app.include_router(state.router)
    app.include_router(settings_router.router)
    app.include_router(reset.router)
    app.include_router(deck.router)
    app.include_router(picks.router)

    return app


app = create_app()
