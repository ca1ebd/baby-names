from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from babynames_api.config import settings
from babynames_api.routers import deck, health, reset, state
from babynames_api.routers import settings as settings_router


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


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
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=str(exc.status_code),
                    message=exc.detail
                )
            ).model_dump(),
            headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
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

    return app


app = create_app()
