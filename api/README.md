# Baby Name Swipe — API

FastAPI service backing accounts, the shared name deck, and offline sync
(spec 002). See `../CLAUDE.md` for the wider project and
`specs/002-backend-accounts-sync/` for the design docs — this file only
covers running and developing the service.

## The gate

```bash
make check          # ruff + pyright --strict + pytest, from the repo root
```

One command, one pass/fail result. It provisions its own throwaway Postgres
via `testcontainers` (Docker must be running) and disposes of it afterward —
nothing to set up first, nothing left running after. This is what to run
after every edit, and what must be green before surfacing a diff.

`make check-web` runs the frontend's equivalent (oxlint + tsc + vite build).

## Working test-first (FR-028)

Every behavioral change in this codebase starts as a test that fails before
the code that satisfies it exists. The loop:

1. Write a test in `api/tests/{contract,integration,unit}/` that describes
   the behavior you want.
2. Run `make check` and confirm it fails **for the right reason** — a test
   that passes the moment you write it hasn't described anything, and a test
   that fails on an import error or a fixture typo isn't testing your change.
3. Implement the smallest thing that makes it pass.
4. Run `make check` again. Fix whatever else it flags — ruff, `pyright
   --strict`, or fallout in other tests.
5. Surface the diff once `make check` is fully green.

`api/tests/` is organized by what the test proves, not by which file it
touches:

- `contract/` — one request against a live endpoint, asserting the response
  shape and status code match `specs/002-backend-accounts-sync/contracts/http-api.md`.
- `integration/` — multi-request scenarios (concurrency, sync convergence,
  cross-account isolation) that need the real database, not a mock.
- `unit/` — pure functions with no I/O (the deck algorithm, JWT verification,
  the rate limiter's math).

**Every new table needs `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` in the
migration that creates it.** The database is a Supabase project, which
auto-exposes every `public`-schema table via PostgREST to anyone holding the
project's anon key — and that key ships in the frontend's JS bundle, so it's
not a secret. RLS is what keeps that path closed; the app itself never needs
it, since the backend connects as the table-owning role and bypasses RLS
regardless. No policies are needed either, for the same reason — enabling RLS
with zero policies just default-denies every non-owner role.
`tests/integration/test_row_level_security.py` runs the real Alembic chain
against a scratch database and fails the build if any table comes out
unprotected, so this isn't optional-and-easy-to-forget — `make check` won't
go green without it.

## Other Makefile targets

```bash
make dev            # uvicorn --reload on :8000, against secrets/.env if present
make migrate        # alembic upgrade head
make seed-corpus    # idempotent load of the 63,880-name corpus
```

`dev`, `migrate`, and `seed-corpus` load `secrets/.env` (repo root,
gitignored) when it exists, so they reach the real Supabase project.
`make check`'s tests never read it — they stay on testcontainers Postgres by
design (research §4: never exercise a real database or real email from
tests).

## Deploying

See `api/DEPLOY.md` for the manual deploy runbook (there is no CI/CD for this
service yet — that's deferred to a later spec).
