"""Entrypoint for the daily scheduled Container Apps job.

A free Supabase project pauses after 7 days without activity and is eventually
deleted (research §2), so this heartbeat is load-bearing, not housekeeping.

It issues `SELECT 1` straight through `db.py` rather than calling `/health`,
deliberately: routing the heartbeat through the HTTP app would make the
database's survival depend on the web app being deployable and healthy. A bug
that takes the API down must not also let the database lapse.

Run as `python -m babynames_api.keepalive`. Exits 0 on a successful ping and 1
on failure, so the job's own run history is the signal — a failing schedule is
visible in `az containerapp job execution list` without reading logs.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from sqlalchemy import text

from babynames_api.db import get_session_factory


def ping() -> None:
    """Touch the database so the free-plan inactivity timer resets."""
    session = get_session_factory()()
    try:
        result = session.execute(text("SELECT 1")).scalar_one()
        if result != 1:
            raise RuntimeError(f"SELECT 1 returned {result!r}")
    finally:
        session.close()


def main() -> int:
    started = datetime.now(UTC)
    try:
        ping()
    except Exception as exc:
        print(f"keepalive FAILED at {started.isoformat()}: {exc}", file=sys.stderr)
        return 1

    elapsed = (datetime.now(UTC) - started).total_seconds()
    print(f"keepalive ok at {started.isoformat()} ({elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
