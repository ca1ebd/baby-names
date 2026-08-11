# Backend Green: Test Failures, Contract Gaps, and Two Real Concurrency Bugs

**Date:** 2026-08-11 03:49
**Branch:** `backend-accounts-sync`
**Status:** ✅ Backend complete and green — `make check` and `make check-web` both
pass. Task list audited and amended; `/speckit-implement` deferred to a separate
session.

## Problem

Picked up 19 failing tests left from the previous session (see
`2026-08-11_0246_fix-backend-test-failures.md`, which ended at 33 passed / 19
failed). The prior session's read was that the remainder were "edge cases and
advanced scenarios." That turned out to understate it: about a third of the
failures were real defects in shipped code, and two were concurrency bugs the
test harness had been hiding rather than exercising.

## Root Causes

Three distinct categories, worth separating because the fix differs.

### 1. Tests asserting against a shape the data model doesn't have (12 failures)

- **Non-UUID account ids.** Eight deck integration tests built accounts with
  readable ids (`"exhaustion-account"`, `"account-1"`, `"shared-deck-account"`).
  `accounts.id` *is* the Supabase `sub` — a uuid column — so every one of them
  died in psycopg before reaching an assertion. Replaced with a `make_account`
  conftest factory that mints a real UUID and both swipers.
- **Invented name strings.** Picks/sync tests swiped `ReplayName0`,
  `SharedName1`, `TestName000`. Picks reference `names.id` and the service owns
  the corpus (FR-012), so those picks were correctly dropped and the tests
  asserted nothing at all. They now draw from a `corpus_names` fixture.
- **Corpus too small / colliding.** The seeded test corpus grew 200 → 300 per
  gender so the 250-name no-repeat contract test has names to be dealt, and
  `test_state_restore` stopped inserting names at girl ranks 0–2, which
  collided with the seeded corpus on `UNIQUE(gender, rank)`.
- **Wrong settings attribute.** Rate-limit tests poked
  `settings.RATE_LIMIT_PER_HOUR`; the attribute is `rate_limit_per_hour`, as
  the unit tests already had it. Two of them also expected a 429 sooner than
  the cap allows, and then read `/v1/state` while still rate-limited.

### 2. Real defects in shipped code (7 failures)

- **`GET /v1/state` never returned `decidedAt`.** The client round-trips that
  value back into `POST /v1/picks` as the last-write-wins tiebreak, so without
  it convergence across two devices cannot work. Added, serialized exactly as
  JavaScript's `toISOString()` (`.000Z`, not `+00:00`) since the string the
  client reads has to be the string it would have produced locally.
- **`accepted` counted only changed rows.** `syncQueue.ts` does
  `outbox.slice(response.accepted)` — it reads `accepted` as "how many entries
  off the head of my outbox you took." Under-reporting made the client delete
  the wrong entries and resend the rest forever. Now counts everything
  acknowledged, including replays that lose the `decidedAt` comparison.
- **A repeated name inside one batch hit a duplicate primary key.** Swipe →
  undo → swipe again is a legitimate outbox, and both entries are the same row.
  The batch is now collapsed onto its own key before anything touches the
  database.
- **A picks flush rewound swiper position.** Position was recomputed from picks
  alone, so a swiper dealt 100 cards who flushed 10 was sent back to position
  10 and re-dealt cards they had already seen. Position is now monotonic:
  `max(current, furthest decided + 1)`.
- **Error envelope wasn't the contract's.** 501 picks returned FastAPI's raw
  422, and every error code was a stringified status number. Added a validation
  handler (400) and semantic codes via a small `errors.py` — `rate_limited`,
  `unauthenticated` — which is what the contract says the client branches on.

### 3. Concurrency bugs the harness was hiding (2 failures)

The `client` fixture handed every request the test's own `Session`. The
concurrent-deal tests therefore collided inside SQLAlchemy
(`This session is provisioning a new connection`) instead of in Postgres, which
is the layer they exist to exercise. Giving each request its own session — as
`db.get_session` does in production — exposed two genuine races:

- **`served_order` extension.** Positions are dense and per-account, so two
  callers that both read "37 names served" both try to write position 37. Now
  serialized by a `FOR UPDATE` lock on the account row, with the whole deal in
  one transaction and one commit.
- **The rate limiter's read-then-insert.** Two simultaneous first-requests in
  an hour both insert `(account_id, window_start)` and one dies on the primary
  key; the read-modify-write also silently lost increments. Now a single
  `INSERT … ON CONFLICT DO UPDATE … RETURNING`, which is the whole reason
  data-model.md put the counter in Postgres rather than in process memory.
  Account provisioning had the identical race and got the identical fix.

## Changes Made

### Backend

- **New** `api/src/babynames_api/errors.py` — `ApiError` plus the status → code
  mapping for the `{"error": {"code", "message"}}` envelope.
- **New** `api/src/babynames_api/state.py` — `load_state()`, so `/v1/state`,
  `/v1/reset`, and `/v1/settings` return one shape from one place.
- `main.py` — semantic error codes, `RequestValidationError` → 400 envelope.
- `auth.py` — provisioning via `ON CONFLICT DO NOTHING`.
- `ratelimit.py` — atomic upsert-and-count; commits the increment before
  raising, so a rejected request can't be retried past the cap.
- `deck.py` — account row lock, single transaction, swiper advance moved in
  from the router.
- `routers/picks.py` — batch collapse, `accepted` semantics, monotonic position.
- `routers/{state,reset,settings}.py` — rate limit as a dependency rather than
  a manual call; reset and settings now return the post-change state per
  contract.
- `schemas/state.py` — `decidedAt` with the JS-compatible serializer.

### Tests

- `conftest.py` — 300-name corpus per gender, `corpus_names` fixture,
  `make_account` factory, and per-request sessions in the `client` fixture.
- Eight deck integration tests, the sync and rate-limit integration tests, and
  `test_state_restore` rewritten against those fixtures.
- Two new tests for behavior nothing pinned down: a batch holding the same name
  twice, and reset returning the post-reset state.

### Frontend

- `src/lib/api.ts` — `decidedAt` on the state pick shape; `putSettings` and
  `postReset` now return `AccountState`.
- `src/lib/auth.ts` — **pre-existing build break**, unrelated to the tests:
  `Session` and `User` were imported as values, not types, so `vite build`
  failed outright and `make check-web` could not run at all on this branch.

## Results

### Before
- **33 passed, 19 failed**
- `make check-web` could not complete — the bundle didn't build

### After
- **53 passed, 0 failed** — ruff clean, `pyright --strict` clean, suite run four
  times to check for flakiness
- `make check-web` green (oxlint + tsc + vite build)

| Category | Passing |
|----------|---------|
| Health / Auth / State / Settings / Reset contract | 15/15 |
| Deck contract + integration | 12/12 |
| Picks contract + sync/rate-limit integration | 14/14 |
| Unit (auth, ratelimit, deck algorithm) | 12/12 |

## Are We Ready?

**The backend is ready. The product is not.** Those are different questions and
it's worth being precise about which is which.

**Ready:**
- All six endpoints implemented, contract-conformant, and covered.
- `make check` is a real single gate: it provisions its own Postgres via
  testcontainers and runs lint, strict types, and tests in ~25s. That is most
  of US4 (T074/T075) in practice, though the tasks stay unchecked until the
  clean-clone and deliberate-failure validations (T077/T078) actually run.

**Not ready — nothing user-visible has changed yet:**
- The app still runs entirely on the bundled corpus and localStorage. T060,
  T061, T069–T073, and T047–T048 are all untouched, so the frontend has never
  made a single call to any of this.
- Nothing is deployed (US5, T080–T089). No Container App, no migrations applied
  to the real Supabase database, no corpus seeded there. `secrets/.env` is
  present on this machine, so those tasks are unblocked; they just haven't run.

**Two sequencing hazards worth deciding on before starting either:**

1. **Staging deploys on every push to a non-main branch.** The moment the
   frontend starts calling the API, `baby-names.test.calebdudley.dev` will be
   calling a service that does not exist. Either deploy the backend (US5)
   before the frontend cutover, or accept a knowingly broken staging site while
   the client work is in flight.
2. **`make seed-corpus` reads `src/lib/nameCorpus.ts` directly** — it parses the
   TypeScript file rather than a generated `names.json` (T027 describes a JSON
   artifact that was never created; the script works, it just reads a different
   source). T061 deletes that file. **The corpus must be seeded into the real
   database before `nameCorpus.ts` is deleted**, or the seeding path is gone
   along with it.

**Recommended next step:** US5 deploy first (T080–T087), because it's
independent of all remaining client work, it unblocks a real
`VITE_API_BASE_URL`, and doing it first defuses hazard 1. Seed the corpus as
part of that (T084 then `make seed-corpus`) and hazard 2 goes with it. Then the
frontend cutover (T060/T061, T069–T073) has something real to talk to.

## Spec Kit Audit and Task List Amendment

Ran `/speckit-analyze` (read-only, per its contract) against spec.md, plan.md,
tasks.md, and the constitution before touching anything. It found no CRITICAL
issues, so implementation was never *blocked* — but three HIGH findings all
detonate during a run rather than before it, and all three sit inside the next
30 tasks.

### What the audit found

| ID | Severity | Finding |
|---|---|---|
| C1 | HIGH | `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` are documented in quickstart.md as frontend **build** variables, but no task injected them into either SWA workflow. `auth.ts` falls back to `''`, `api.ts` to `localhost:8000` — so a deployed bundle fails at **runtime** with a perfectly green build, and sign-in is simply dead |
| F1 | HIGH | T061 deletes `src/lib/nameCorpus.ts`; `seed_corpus.py` parses that exact file. Nothing sequenced seeding before deletion |
| U1 | HIGH | T027 was checked complete, but its named artifact `api/src/babynames_api/corpus/names.json` never existed. A checked box means `/speckit-implement` never revisits it — the gap was invisible and permanent |
| F2 | MEDIUM | Every push to a non-`main` branch auto-deploys staging; from T060 on, staging would serve an app calling a service US5 hadn't deployed |
| C2/C3 | MEDIUM | SC-002, SC-011, SC-012 had no task reference — covered only implicitly by T092 |
| D1 | MEDIUM | plan.md's gate correctly flagged the constitution's stale name-pool invariants and recommended a PATCH amendment, but nothing tracked it, so it would have died at feature close |
| A1 | LOW | T074/T075 wording — left open deliberately |

Also confirmed two things that looked like problems and are not: Principle III's
manual backend deploy is an owner-granted, time-boxed deviation already
recorded in plan.md's Complexity Tracking, and Principle IV's "never discard
picks" is satisfied because spec.md:50 establishes the app is pre-release with
nothing to migrate.

### What changed in tasks.md

- **T027 reopened** (`[X]` → `[ ]`) with a dated note: generate the JSON artifact
  and repoint the script at it, so the backend stops depending on a frontend
  file. This fixes the false-complete *and* removes F1 structurally rather than
  just scheduling around it.
- **T094** (new, US5) — seed the corpus into the real database after migrations;
  blocks T061.
- **T095** (new, US5) — wire the three `VITE_` vars into both workflows from
  repository secrets, preserving `VITE_COMMIT_SHA` stamping (Principle III).
- **T096** (new, Phase 8) — the PATCH `/speckit-constitution` amendment.
- **T092** now cites SC-002, SC-011, SC-012 explicitly.
- **Dependencies section** gained a "Cross-phase blocking dependencies"
  subsection; T061 carries an inline blocked-by; Implementation Strategy
  reordered to deploy-before-client-cutover.

**Every task ID stayed stable.** No renumbering, no reordering of task lines —
roughly 40 cross-references live in the Dependencies, Parallel Example, and
Implementation Strategy sections, and renumbering would have silently broken
the traceability the framework exists to provide. Ordering constraints went
into the Dependencies section, which is the framework's native home for them.

### The amendment's own fallout

Editing the task list broke three things elsewhere in it, caught on the
re-analysis pass and fixed: Phase 7's goal still described only "container,
migrations, keepalive job"; Parallel Team Strategy still called US5 "fully
independent of US1–US3"; and T081's runbook task enumerated only "T082–T087 in
order," so `DEPLOY.md` would have been written without the seed and workflow
steps. A task-list edit has the same blast radius as a code edit and needs the
same check afterward.

### Verification

96 tasks, zero duplicate IDs, no gaps across T001–T096, and every `T0xx`
reference in the file resolves to a real task. SC explicit coverage 11/12 (up
from 8/12; SC-007 is a post-launch invoice check, correctly excluded).
Post-amendment severity counts: **Critical 0, High 0, Medium 0, Low 1**.
Constitution V scan clean — the only hits are `CLAUDE.md` filename references,
the constitution's own permitted functional exception.

## Next Session

`/speckit-implement` was deliberately **not** run — it's being started fresh in
its own session. Two things that session needs to know:

1. **It will start at T027**, now the first unchecked task, which generates the
   corpus artifact everything downstream depends on. That is the correct entry
   point.
2. **`/speckit-implement` walks phases in order, so left alone it reaches T061
   (Phase 4) before T094 (Phase 7)** — the exact hazard the amendment exists to
   prevent. The blocking note is in the file in three places, but tell that
   session explicitly to honor the cross-phase blocking dependencies, or to run
   US5's T082–T085, T094, and T095 first.

T082–T087 create real Azure resources and T095 sets repository secrets; those
are worth confirming interactively rather than provisioning unattended.

## Key Learnings

1. **A test that invents its own data can assert nothing.** Six of these tests
   swiped names the corpus never had; the service correctly dropped every one,
   and the tests still "ran." A fixture that hands out real corpus names is the
   difference between a test and a formality.
2. **A shared test session doesn't test concurrency, it prevents it.** Both
   races found here were invisible until each request got its own session.
   Test harnesses that diverge from production wiring hide exactly the class of
   bug the tests were written to catch.
3. **`accepted` is a protocol, not a statistic.** The client slices its outbox
   by that number. Any definition other than "entries consumed off the head of
   your batch" corrupts the queue, and no server-side test would have noticed —
   it took reading `syncQueue.ts` to see it.
4. **Position has two plausible meanings** — furthest dealt vs. furthest swiped
   — and the deck and sync paths had quietly picked different ones. Making it
   monotonic satisfies both without having to relitigate the definition.
5. **A checked box is a claim, and claims decay.** T027 was marked complete with
   half its deliverable missing, which made the gap permanent: the implement
   flow never revisits a checked task. Two of the three HIGH findings traced
   back to that single stale checkbox. Auditing what the task list *asserts* against
   what is on disk is worth doing before resuming, not after.
6. **The failures that survive to production are the ones with green builds.**
   C1's missing `VITE_` wiring, F1's deleted seeder input, and the "accepted"
   protocol bug share a shape: every one of them passes lint, types, and tests,
   and fails only in front of a user. Reading the consumer — the workflow file,
   the deleted import, `syncQueue.ts` — found all three; no amount of running
   the suite would have.
