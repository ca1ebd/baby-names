# Implementation Plan: Backend, Accounts & Sync

**Branch**: `backend-accounts-sync` | **Date**: 2026-08-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-backend-accounts-sync/spec.md`

## Summary

Move the app's state off the device. A FastAPI service owns the name corpus,
each account's deck order, both swipers' picks, and the record of what was
served; the browser keeps a block of names it can swipe through with no
connection and syncs when it reconnects. Accounts come from Supabase Auth by
passwordless magic link, and the service verifies those sessions offline
against Supabase's JWKS.

The design is shaped by three research findings more than by anything else: a
$0 bill is achievable on Container Apps only with a Consumption environment
scaled to zero; a free Supabase project **pauses after 7 days of inactivity and
is eventually deleted**, so a scheduled heartbeat is mandatory rather than
optional; and Supabase's built-in email sender cannot deliver magic links to
anyone outside the project team, so a third-party SMTP provider is a hard
dependency. See [research.md](research.md).

Deck order is reproduced from the frontend's existing algorithm bit-for-bit,
including a float64 underflow that makes ~71% of the core sort by strict rank —
faithfully, not "correctly," because feature parity is this feature's whole
premise.

## Technical Context

**Language/Version**: Python 3.12 (service); TypeScript/React 19 (existing client)

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync) + psycopg 3,
Alembic, PyJWT + JWKS client, `supabase-js` on the client

**Storage**: PostgreSQL (Supabase-hosted, free plan). `babyname-swipe-v3` in
localStorage is demoted from system-of-record to offline cache.

**Testing**: pytest with testcontainers-python (throwaway Postgres per session);
`ruff` + `pyright --strict` in the same gate

**Target Platform**: Linux container on Azure Container Apps (Consumption,
`minReplicas: 0`); client stays on Azure Static Web Apps

**Project Type**: Web application — existing SPA frontend plus a new backend service

**Performance Goals**: first card within 3 s of completing sign-in (SC-001),
including a cold start absorbed by the warm-up during sign-in; a full block
swipeable offline with no perceptible delay (FR-018)

**Constraints**: $0/month recurring, hard stop (FR-024); free tiers only;
offline-capable for one block; no CI/CD this release; `pyright --strict` clean;
every change test-first

**Scale/Scope**: 1–2 accounts initially, designed to not fall over at hundreds.
63,880 corpus names. ~200 hours/month of free container time available; expected
usage is a rounding error against it.

## Constitution Check

*GATE: evaluated before Phase 0, re-evaluated after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Muted Visual Design | **PASS** | The sign-in screen is new UI and adopts the existing palette, minimal motion, `fontSize: 16` inputs, safe-area insets, `minWidth: 0` on flex children. No new visual language. |
| II. Cost Consciousness | **PASS with conditions** | $0 target with a documented cost profile (research §1), spend safeguards (FR-032 rate cap, Azure spend alert), cheapest viable tiers. Two config details are load-bearing: Consumption workload profile and `minReplicas: 0`. Adds one new external dependency — a free-tier SMTP provider (research §4). |
| III. Pipeline-Only Deployments | **VIOLATION — justified** | Backend deploys are manual this release. Time-boxed deviation granted by the owner 2026-08-10; see Complexity Tracking. Frontend remains pipeline-only and untouched. |
| IV. Storage Key Stability | **PASS** | `babyname-swipe-v3` keeps its name. Its value is reshaped (block cache + unsynced-pick queue), which the principle permits — schema evolution happens inside the value. Pre-release, so no save in the wild is affected. |
| V. No AI Vendor Attribution | **PASS** | Branch, commits, and artifacts are clean. |
| *Constraint*: no backend by default | **APPROVED** | This spec is the explicit approval the constraint requires. |
| *Constraint*: name pool invariants | **STALE — needs amendment** | See below. Not a violation by this plan. |

### Gate finding: the constitution's name-pool invariants are out of date

The Additional Constraints section requires "no names starting with 'D', none
ending in 'y'/'ie'/'ey' … and deterministic fixed-seed deck ordering across
devices." Two of those four clauses no longer describe the project:

- The letter rules were **retired by spec 001**, which replaced the hand-built
  pool with the full SSA corpus on the explicit reasoning that narrowing the
  deck is the criteria filter's job. They have been wrong since 001 merged.
- **Fixed-seed ordering across devices** is retired by this spec's FR-014, which
  gives each account its own seed. The property that mattered — two swipers
  seeing the same deck — is now provided by the account rather than by a global
  constant, and is strictly better for it.

The remaining two clauses (zero girl/boy spelling overlap, deterministic
ordering) still hold and this plan preserves both.

**This does not block the gate** — no work in this plan violates the
constitution's intent — but the document should be amended so it stops
describing a pool that has not existed since 001. Recommended as a PATCH-level
`/speckit-constitution` update, separate from this feature's branch.

### Post-Phase 1 re-evaluation

Re-checked after the design below was complete. No new violations. The design
adds one thing the initial check did not anticipate: a **scheduled keep-alive
workflow** (research §2). It is not a deploy and not CI/CD — it builds nothing
and ships nothing — so it neither breaches Principle III nor the spec's
deferral of CI/CD to the next spec. It is included here because without it the
free database pauses in 7 days and is eventually deleted, which no amount of
application code can survive.

## Project Structure

### Documentation (this feature)

```text
specs/002-backend-accounts-sync/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── http-api.md      # Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks output — not created here
```

### Source Code (repository root)

```text
Makefile                     # `make check` — the gate the agent runs after every edit
api/
├── pyproject.toml           # deps, ruff + pyright config
├── Dockerfile
├── alembic.ini
├── migrations/versions/     # ordered, versioned schema changes
├── src/babynames_api/
│   ├── main.py              # app factory, router wiring
│   ├── config.py            # env-derived settings (Pydantic Settings)
│   ├── db.py                # engine, session dependency
│   ├── auth.py              # JWKS fetch/cache, JWT verification dependency
│   ├── ratelimit.py         # Postgres fixed-window cap (FR-032)
│   ├── models/              # SQLAlchemy Mapped[...] declarative models
│   ├── schemas/             # Pydantic v2 request/response models
│   ├── deck.py              # LCG + weighted shuffle, faithful float64 port
│   ├── routers/             # health, state, settings, deck, picks
│   └── corpus/names.json    # generated, shared source with the client corpus
└── tests/
    ├── conftest.py          # session-scoped Postgres container, per-test rollback
    ├── contract/            # endpoint shape + auth + rate-limit behavior
    ├── integration/         # deal → swipe offline → sync → converge
    └── unit/                # deck ordering fidelity, migration/backfill logic

src/                         # existing frontend
├── BabyNameSwipe.tsx        # sign-in screen, block cache, sync queue, corpus removal
└── lib/
    ├── api.ts               # NEW — typed client for the service
    ├── auth.ts              # NEW — supabase-js session handling
    ├── syncQueue.ts         # NEW — offline pick queue, idempotent flush
    ├── storage.ts           # unchanged shim; cached value's shape changes
    └── nameCorpus.ts        # DELETED — ~217 KB gzip removed from the bundle

.github/workflows/
├── azure-static-web-apps.yml          # unchanged (prod frontend)
├── azure-static-web-apps-staging.yml  # unchanged (staging frontend)
└── keepalive.yml                      # NEW — daily GET /health; not a deploy
```

**Structure Decision**: The service lives in `api/` at the repo root beside the
existing frontend, rather than in a separate repository. One repo keeps the
contract, the client that consumes it, and the spec in a single commit and a
single review — worth more at this size than the isolation a split would buy.
`make check` sits at the root because that is where the agent runs it; it drives
the `api/` toolchain. Frontend checks stay on npm and are reachable as
`make check-web`, so the Python gate stays exactly the single command the spec
asked for.

## Approach by requirement group

**Accounts (FR-001–006)**. `supabase-js` handles the magic-link round-trip
entirely on the client; the backend never sees a credential. Every request
carries the Supabase JWT, verified offline against cached JWKS (research §3).
The account id *is* the Supabase user id, so there is no user table to keep in
sync. Signing out clears the cached block and any unsynced picks after a
flush attempt.

**Parity and state (FR-007–011)**. The service stores the same object the app
persists today, normalized: swiper labels and positions, last name, gender
filter, onboarded flag, and picks keyed by name. Matches stay derived from
picks (FR-009), preserving 001's guarantee. Backup/restore keeps working
against the account rather than the device.

**Names and order (FR-012–017)**. The corpus is seeded into Postgres from the
same generated source the client used, then deleted from the bundle. Blocks are
dealt by running the faithful float64 port of `weightedShuffle` under the
account's seed, skipping anything already in `served_order`, and appending the
result. Because `served_order` is append-only and unique per (account, name),
FR-015's no-duplicates guarantee is a database constraint rather than
application logic.

**Offline and sync (FR-018–023)**. The client holds one block plus a queue of
unsynced picks. Sync is a single idempotent upsert batch keyed by
(account, slot, name) with a client timestamp, so retries and interleaved
devices converge on last-write-wins (FR-023) without coordination. The next
block is requested at a low-water mark, not at exhaustion.

**Cost and abuse (FR-024, FR-032)**. Consumption environment, `minReplicas: 0`,
free Supabase plan, free SMTP tier, Azure spend alert at any nonzero amount.
Rate limiting is a Postgres fixed-window row per (account, hour) — see
research §6 for why in-memory counting would enforce nothing here.

**Cold start and liveness (FR-030, FR-031)**. The client fires `GET /health`
on load, before sign-in, so the container wakes and the database is touched
while the user is still reading the sign-in screen. The same endpoint is what
the daily keep-alive workflow hits. Every waking/unreachable/rate-limited state
renders as the one friendly waiting state, never an error.

**Dev loop (FR-026–028)**. `make check` runs `ruff check`, `pyright --strict`,
and `pytest` against a testcontainers Postgres, reporting one pass/fail. Every
change starts as a failing test (FR-028); the agent runs the gate after each
edit and fixes its own failures before surfacing a diff.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| **Principle III — manual backend deploys** (time-boxed deviation, granted by the owner 2026-08-10; scope: backend and database only; expiry: the next spec, which covers backend CI/CD; does not renew without a fresh grant) | Automating a deploy path before it has been walked once by hand encodes guesses. The first manual deploys are how the project learns what the pipeline must actually do — what to configure, what breaks, in what order. | Building CI/CD first would mean writing a pipeline against an unknown target and then rewriting it once reality arrived. Compensating controls while the deviation is in force: `make check` as the gate (FR-027, FR-028), a written runbook rather than improvisation (FR-025), ordered versioned migrations (FR-026), and a health signal that makes a broken deploy visible without reading logs (FR-029). |
| **A server-side component at all** | The spec is the explicit approval the constitution's "no backend by default" constraint requires: durability, accounts, and every later feature depend on it. | Staying local-only was the status quo this spec exists to end; a cleared browser cache is unrecoverable loss and no local design fixes that. |
