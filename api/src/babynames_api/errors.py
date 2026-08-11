"""
The `{"error": {"code", "message"}}` envelope's vocabulary.

contracts/http-api.md names three codes the client actually branches on —
`rate_limited`, `unauthenticated`, `corpus_exhausted` — and says everything else
renders as the single friendly waiting state (FR-031). So the code has to be a
stable string, not the numeric status: a client that switched on "429" would be
reading an HTTP detail it should never have had to know about.

An endpoint that needs a code other than its status's default raises
`ApiError(...)` with one explicitly.
"""

from typing import Any

from fastapi import HTTPException

# Status → the code a client sees when nothing more specific was raised.
_DEFAULT_CODES: dict[int, str] = {
    400: "invalid_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    429: "rate_limited",
}


class ApiError(HTTPException):
    """An HTTPException that carries the envelope's `code` explicitly."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code


def error_code_for_status(exc: Any, status_code: int) -> str:
    """The envelope code for an exception: its own if it has one, else the default."""
    code = getattr(exc, "code", None)
    if isinstance(code, str):
        return code
    return _DEFAULT_CODES.get(status_code, "server_error")
