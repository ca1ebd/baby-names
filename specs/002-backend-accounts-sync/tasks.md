---

description: "Task list template for feature implementation"
---

# Tasks: Backend, Accounts & Sync

**Input**: Design documents from `/specs/002-backend-accounts-sync/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md, quickstart.md (all present)

**Tests**: Included. The spec's FR-028 mandates test-first development ("every behavioral change MUST originate as a test that fails before the implementation that satisfies it exists"), and User Story 4 is explicitly about that loop — so test tasks are not optional here.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P3) so each can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps the task to US1–US5 from spec.md
- File paths are exact and match plan.md's Project Structure

## Path Conventions

Per plan.md: the service lives in `api/` at the repo root; the existing frontend stays in `src/`. New client files: `src/lib/api.ts`, `src/lib/auth.ts`, `src/lib/syncQueue.ts`. `src/lib/nameCorpus.ts` is deleted in Phase 4.

## Credentials available on the implementing machine

Not available to the planning session, but present wherever `/speckit-implement` actually runs — implementation tasks should use these rather than creating new accounts/projects or prompting for values:

- **Supabase**: an API key/connection string for a Supabase project already tied to the owner's account, at `secrets/.env` (repo root, gitignored — see T006). It has the same shape as `api/.env.example` (T005): `DATABASE_URL`, `SUPABASE_PROJECT_REF`, etc. Local dev, `make seed-corpus`, and the deploy tasks read it directly; `make check`'s tests never touch it (they stay on testcontainers, per research §4's "never exercise real email/production DB from tests").
- **Azure**: the `az` CLI is already authenticated on that machine, and the `baby-names-rg` resource group (East US 2 — the same one hosting the frontend's Static Web Apps, per CLAUDE.md) already exists. US5's provisioning tasks (T082–T087) create Container Apps resources *inside* that existing group rather than a new subscription, login flow, or resource group.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up the `api/` project skeleton and the tooling `make check` will run against.

- [ ] T001 Create the `api/` skeleton per plan.md's Project Structure: `api/pyproject.toml`, `api/Dockerfile`, `api/alembic.ini`, `api/migrations/versions/`, `api/src/babynames_api/{models,schemas,routers,corpus}/`, `api/tests/{contract,integration,unit}/`
- [ ] T002 [P] Populate `api/pyproject.toml` with runtime deps (FastAPI, Pydantic v2, SQLAlchemy 2.0, `psycopg[binary,pool]` 3, Alembic, PyJWT, uvicorn) and dev deps (ruff, pyright, pytest, `testcontainers[postgres]`)
- [ ] T003 [P] Configure ruff and `pyright --strict` for `api/` in `api/pyproject.toml`
- [ ] T004 [P] Create `api/Dockerfile` — Python 3.12 slim base, installs `api/pyproject.toml` deps, runs `uvicorn babynames_api.main:app`
- [ ] T005 [P] Create `api/.env.example` documenting `DATABASE_URL`, `SUPABASE_PROJECT_REF`, `CORS_ORIGINS`, `RATE_LIMIT_PER_HOUR`, `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` per quickstart.md's Environment table — placeholders only. The real Supabase project's values live in `secrets/.env` at the repo root on the implementing machine (see "Credentials available on the implementing machine" above); never copy them into this file
- [ ] T006 [P] Add `secrets/` to `.gitignore` — FR-025 requires the repository contain no credentials, and `secrets/.env` is where the real Supabase key lives on the implementing machine
- [ ] T007 Create the root `Makefile` with `check`, `check-web`, `dev`, `migrate`, `seed-corpus` targets per quickstart.md's "The gate"; `dev`, `migrate`, and `seed-corpus` load `secrets/.env` when present so they reach the real Supabase project, while `check` stays testcontainers-only and never reads it
- [ ] T008 [P] Add `@supabase/supabase-js` to `package.json` dependencies for client-side auth

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, auth, rate limiting, health, and the test harness — everything every user story's endpoints depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T009 Initialize Alembic (`api/alembic.ini`, `api/migrations/env.py`) pointed at the SQLAlchemy declarative `Base` metadata
- [ ] T010 [P] Create `api/src/babynames_api/config.py` — Pydantic Settings model that loads `secrets/.env` from the repo root when present (falling back to `api/.env` / process env otherwise), so `make dev`/deploy tooling reaches the real Supabase project with nothing hardcoded or committed
- [ ] T011 [P] Create `api/src/babynames_api/db.py` — sync SQLAlchemy engine (psycopg 3) + `get_session` dependency
- [ ] T012 [P] Create the `Name` model in `api/src/babynames_api/models/name.py` — `id`, `name` (UNIQUE), `gender`, `rank`, `is_core`; `UNIQUE(gender, rank)` (data-model.md `names`)
- [ ] T013 [P] Create the `Account` model in `api/src/babynames_api/models/account.py` — `id` (uuid PK = Supabase `sub`), `deck_seed`, `last_name`, `gender_filter`, `onboarded`, `created_at`
- [ ] T014 [P] Create the `Swiper` model in `api/src/babynames_api/models/swiper.py` — `account_id` FK, `slot`, `label`, `position`; PK `(account_id, slot)`; CHECK `slot IN (0, 1)`
- [ ] T015 [P] Create the `ServedOrder` model in `api/src/babynames_api/models/served_order.py` — `account_id` FK, `position`, `name_id` FK; PK `(account_id, position)`; `UNIQUE(account_id, name_id)`
- [ ] T016 [P] Create the `Pick` model in `api/src/babynames_api/models/pick.py` — `account_id`, `slot`, `name_id`, `verdict`, `decided_at`; PK `(account_id, slot, name_id)`
- [ ] T017 [P] Create the `RateLimitWindow` model in `api/src/babynames_api/models/rate_limit_window.py` — `account_id`, `window_start`, `request_count`; PK `(account_id, window_start)`
- [ ] T018 Generate the initial Alembic migration creating all six tables with the constraints from T012–T017 in `api/migrations/versions/`
- [ ] T019 [P] Create `api/tests/conftest.py` — session-scoped `testcontainers` `PostgresContainer`, `alembic upgrade head` run once, per-test transaction rollback, and a fixture that mints JWTs directly against a JWKS test fixture. Tests MUST NOT read `secrets/.env` or touch the real Supabase project (research §4)
- [ ] T020 [P] Unit test: an unsigned, expired, or malformed JWT is rejected and a validly-signed one resolves to its `sub` in `api/tests/unit/test_auth.py`
- [ ] T021 Create `api/src/babynames_api/auth.py` — JWKS fetch/cache keyed off `SUPABASE_PROJECT_REF` from config, offline JWT verification dependency, and account-provisioning-on-first-request (creates the account, its two swipers, and `deck_seed` for an unknown but valid `sub`)
- [ ] T022 [P] Unit test: a fixed-window rate limiter allows requests under the cap, returns 429 with `Retry-After` once exceeded, and resets on window rollover, in `api/tests/unit/test_ratelimit.py`
- [ ] T023 Create `api/src/babynames_api/ratelimit.py` — Postgres fixed-window per-`(account, hour)` dependency (FR-032)
- [ ] T024 [P] Contract test: `GET /health` returns 200 `{"status":"ok","database":"ok",...}` when the database is reachable and 503 degraded when it is not, in `api/tests/contract/test_health.py`
- [ ] T025 Create `api/src/babynames_api/routers/health.py` — `GET /health`, unauthenticated, unversioned, issues `SELECT 1`
- [ ] T026 Create `api/src/babynames_api/main.py` — app factory, CORS from config, the `{"error":{"code","message"}}` error envelope, wires the health router
- [ ] T027 [P] Create `api/scripts/seed_corpus.py` and `api/src/babynames_api/corpus/names.json` (generated from the same source as `src/lib/nameCorpus.ts`) — idempotent load into `names`, wired to `make seed-corpus`, targeting the real project via `secrets/.env`'s `DATABASE_URL`
- [ ] T028 Confirm `make check` runs green (ruff + `pyright --strict` + pytest against testcontainers Postgres) on the empty-but-wired scaffold before any user story work begins

**Checkpoint**: Foundation ready — schema, auth, rate limiting, health, and the test harness all exist; user story implementation can now begin.

---

## Phase 3: User Story 1 - Your swipes belong to you, not to a browser (Priority: P1) 🎯 MVP

**Goal**: An account holds both swipers' state; signing in on any device restores it exactly.

**Independent Test**: Sign in, swipe a distinctive set of names, sign in as the same account in a fresh browser profile, and verify picks, matches, profile names, and gender filter all match. (Card *content* depends on US2; this story proves state ownership and restore.)

### Tests for User Story 1 ⚠️

- [ ] T029 [P] [US1] Contract test: `GET /v1/state` without a token returns 401; with another account's token it returns only that account's data (SC-006) in `api/tests/contract/test_state_auth.py`
- [ ] T030 [P] [US1] Contract test: `GET /v1/state` returns the account/swipers/picks shape from contracts/http-api.md in `api/tests/contract/test_state_get.py`
- [ ] T031 [P] [US1] Contract test: `PUT /v1/settings` updates account+swipers and leaves `served_order` untouched on a `genderFilter` change in `api/tests/contract/test_settings_put.py`
- [ ] T032 [P] [US1] Contract test: `POST /v1/reset` with `scope=everything` clears picks/served_order/positions and sets `onboarded=false`; `scope=swiper` clears only that slot, in `api/tests/contract/test_reset.py`
- [ ] T033 [P] [US1] Integration test: the first authenticated request from an unknown `sub` provisions an account with two swipers and a `deck_seed` in `api/tests/integration/test_account_provisioning.py`
- [ ] T034 [P] [US1] Integration test: signing in from a fresh session restores 100% of picks, matches, labels, last name, and gender filter (SC-001) in `api/tests/integration/test_state_restore.py`

### Implementation for User Story 1

- [ ] T035 [US1] Create Pydantic schemas for state/settings/reset in `api/src/babynames_api/schemas/state.py`
- [ ] T036 [US1] Implement `GET /v1/state` in `api/src/babynames_api/routers/state.py`
- [ ] T037 [US1] Implement `PUT /v1/settings` in `api/src/babynames_api/routers/settings.py`
- [ ] T038 [US1] Implement `POST /v1/reset` in `api/src/babynames_api/routers/reset.py`
- [ ] T039 [US1] Wire state/settings/reset routers into `api/src/babynames_api/main.py`
- [ ] T040 [P] [US1] Create `src/lib/auth.ts` — `supabase-js` magic-link sign-in/out and session persistence
- [ ] T041 [P] [US1] Create `src/lib/api.ts` — typed client with `getState`/`putSettings`/`postReset` (extended by later stories)
- [ ] T042 [US1] Add the sign-in screen to `src/BabyNameSwipe.tsx` — full-page magic-link entry gating Welcome/Swipe, existing muted palette, `fontSize: 16` inputs, safe-area insets
- [ ] T043 [US1] Fire `GET /health` as a warm-up on app load, before sign-in, silently ignoring failure (FR-030) in `src/BabyNameSwipe.tsx`
- [ ] T044 [US1] Wire the Welcome and Settings screens in `src/BabyNameSwipe.tsx` to persist via `PUT /v1/settings` on the existing ~400ms debounce
- [ ] T045 [US1] Wire "RESET EVERYTHING ON THIS DEVICE" and "START [NAME] OVER" to `POST /v1/reset`, updating the confirmation copy to say the reset clears both the account and the device (edge case)
- [ ] T046 [US1] On successful sign-in, call `GET /v1/state` and hydrate the `babyname-swipe-v3` cache per data-model.md's client cache shape
- [ ] T047 [US1] Update `src/lib/storage.ts`'s cached-value handling for the new account/swipers/block/picks/outbox/`syncedAt` shape, keeping `STORAGE_KEY` unchanged (Constitution IV)
- [ ] T048 [US1] On sign-out, attempt a flush once then clear the cached block/picks/account from the device (FR-006)

**Checkpoint**: US1 is independently testable — sign in, restore state on a fresh session, sign out with nothing lost.

---

## Phase 4: User Story 2 - The name list comes from the service (Priority: P1)

**Goal**: The corpus and deck ordering move server-side, byte-for-bit faithful to today's client algorithm.

**Independent Test**: With the frontend's bundled corpus removed, load the app and verify the first cards are real names in the tuned familiar-first order, correctly gendered, honoring the active filter.

### Tests for User Story 2 ⚠️

- [ ] T049 [P] [US2] Unit test: the Python `weightedShuffle` port matches the frontend's float64 semantics exactly — ~71.6% of a 7,457-entry core underflows to key `0.0` first at rank 230, dealt order is strict rank past ~position 2,118, median rank of the first 20 cards is 180–235 (research §5) in `api/tests/unit/test_deck_algorithm.py`
- [ ] T050 [P] [US2] Contract test: `POST /v1/deck/next` returns a block honoring the account's `gender_filter` and never repeats a name across calls (FR-015) in `api/tests/contract/test_deck_next.py`
- [ ] T051 [P] [US2] Integration test: two accounts with the same `gender_filter` get visibly different orders, and each account's own order is reproducible across repeated runs (SC-004) in `api/tests/integration/test_deck_per_account_seed.py`
- [ ] T052 [P] [US2] Integration test: both swipers on one account, and the same account on a second device, are dealt the identical order (US2 scenario 5) in `api/tests/integration/test_deck_shared_order.py`
- [ ] T053 [P] [US2] Integration test: requesting past the end of the corpus for a filter returns `exhausted: true` with a short/empty block rather than repeating or silently emptying (FR-017) in `api/tests/integration/test_deck_exhaustion.py`
- [ ] T054 [P] [US2] Integration test: concurrent `POST /v1/deck/next` calls for the same account never double-deal a name, relying on the `UNIQUE(account_id, name_id)` constraint in `api/tests/integration/test_deck_concurrent_deal.py`

### Implementation for User Story 2

- [ ] T055 [US2] Port `weightedShuffle` faithfully — float64 `key = u^(rank+1)` from the seeded LCG, stable sort by `(key DESC, rank ASC)` — in `api/src/babynames_api/deck.py`
- [ ] T056 [US2] Implement block dealing in `api/src/babynames_api/deck.py` — read the swiper's position, extend `served_order` via the account-seeded shuffle (skipping already-served names) when the run would exceed it, append, then slice the requested count
- [ ] T057 [US2] Create Pydantic schemas for the deck request/response in `api/src/babynames_api/schemas/deck.py`
- [ ] T058 [US2] Implement `POST /v1/deck/next` in `api/src/babynames_api/routers/deck.py`, wired into `main.py`
- [ ] T059 [US2] Extend `src/lib/api.ts` with `requestNextBlock(slot, count)`
- [ ] T060 [US2] Replace the client-side pool/deal logic in `src/BabyNameSwipe.tsx` with backend-served blocks, keeping the card presentation, per-card gender color band, and "both" neutral tone unchanged
- [ ] T061 [US2] Delete `src/lib/nameCorpus.ts` and its import from `src/BabyNameSwipe.tsx` (SC-010, ~217 KB gzip)
- [ ] T062 [US2] Run `scripts/validate-corpus-ui.mjs` (or equivalent) to confirm deck presentation and bundle size are unaffected by the corpus removal

**Checkpoint**: US1 + US2 together let a signed-in user swipe a real, correctly-ordered, correctly-gendered deck end to end.

---

## Phase 5: User Story 3 - Swipe a whole block with no signal (Priority: P1)

**Goal**: A loaded block swipes fully offline; picks queue locally and sync losslessly when connectivity returns.

**Independent Test**: Load a block, disable the network, swipe the entire block, re-enable the network, and verify every pick reached the service in the right order with no duplicates and no losses.

### Tests for User Story 3 ⚠️

- [ ] T063 [P] [US3] Contract test: `POST /v1/picks` upserts on `(account_id, slot, name_id)`, keeping the later `decidedAt` on a repeated or overlapping batch, and accepts picks for names outside the swiper's current block, in `api/tests/contract/test_picks_post.py`
- [ ] T064 [P] [US3] Integration test: interrupting and retrying a sync flush at 20 randomized points converges to the same state as one clean sync — no duplicated, dropped, or reordered picks (SC-005) in `api/tests/integration/test_sync_idempotency.py`
- [ ] T065 [P] [US3] Integration test: a 429 from the rate cap never causes the client-visible pick count to drop (FR-032 client contract) in `api/tests/integration/test_picks_rate_limited.py`

### Implementation for User Story 3

- [ ] T066 [US3] Create Pydantic schemas for the picks batch request/response in `api/src/babynames_api/schemas/picks.py`
- [ ] T067 [US3] Implement `POST /v1/picks` — batched upsert, recomputed swiper positions in the response, capped at 500 picks/request — in `api/src/babynames_api/routers/picks.py`, wired into `main.py`
- [ ] T068 [P] [US3] Create `src/lib/syncQueue.ts` — outbox append on every swipe, ordered flush, delete-only-acknowledged entries, safe retry
- [ ] T069 [US3] Wire `src/BabyNameSwipe.tsx`'s swipe/undo actions to update the local block/picks cache and append to the outbox synchronously, before any network call
- [ ] T070 [US3] Implement the single friendly waiting state (FR-031) in `src/BabyNameSwipe.tsx` for offline/waking/429/5xx, replacing any raw error UI
- [ ] T071 [US3] Implement low-water-mark refill — call `requestNextBlock` at ~20 names remaining (FR-021) in `src/BabyNameSwipe.tsx`
- [ ] T072 [US3] Wire `syncQueue` flush triggers — on reconnect, on next-block request, and on sign-out — in `src/lib/syncQueue.ts`
- [ ] T073 [US3] Implement the corpus-exhausted message, distinct from the offline waiting state (FR-017/FR-022), in `src/BabyNameSwipe.tsx`

**Checkpoint**: US1 + US2 + US3 complete the P1 slice — full offline-capable swiping with sync. This is the MVP.

---

## Phase 6: User Story 4 - A dev loop the agent can run unattended (Priority: P2)

**Goal**: `make check` is a single, reliable, self-contained gate for every future change.

**Independent Test**: On a clean clone with no database running, `make check` provisions its own throwaway Postgres, runs all three tools, and reports a single pass/fail. Deliberately break a type and a test, and confirm it fails for both reasons with actionable output.

- [ ] T074 [US4] Finalize the `Makefile` `check` target to run ruff, `pyright --strict`, and pytest (via testcontainers) as one pass/fail command
- [ ] T075 [US4] Add `make check-web` (oxlint + `tsc` + `vite build`) and confirm `make dev`, `make migrate`, `make seed-corpus` each work standalone
- [ ] T076 [US4] Document the test-first loop (write a failing test → implement → `make check` → fix fallout → surface diff) in `api/README.md`
- [ ] T077 [US4] Validate on a clean clone with no database running: `make check` provisions its own Postgres, runs all three tools, and reports one result in under 5 minutes (SC-008)
- [ ] T078 [US4] Validate failure reporting: temporarily break a type and a test, confirm `make check` fails and names both reasons, then revert
- [ ] T079 [US4] Trace every FR delivered by US1–US3 to the test that failed before its implementation existed (SC-008); note and close any gap

**Checkpoint**: The dev loop is trustworthy enough to be the only gate until CI/CD ships in the next spec.

---

## Phase 7: User Story 5 - Hand-deploy the service (Priority: P3)

**Goal**: A documented, repeatable manual deploy — container, migrations, keepalive job — with zero credentials in the repo, using the `az` CLI session and `baby-names-rg` resource group already available on the implementing machine (see "Credentials available on the implementing machine" above).

**Independent Test**: Follow the written deploy runbook from scratch on a clean environment and reach a working service, with no credential present in the repository at any point.

- [ ] T080 [P] [US5] Create `api/src/babynames_api/keepalive.py` — entrypoint for the daily scheduled Container Apps job, issues a direct `SELECT 1` against the database via `db.py`, independent of the HTTP app
- [ ] T081 [P] [US5] Write `api/DEPLOY.md` — the manual deploy runbook. State plainly that `az` is already authenticated on the deploying machine and `baby-names-rg` (East US 2) already exists alongside the frontend's SWA resources — no new subscription, login, or resource group is created — and that Supabase credentials come from `secrets/.env` rather than a freshly-created project; document each `az` command from T082–T087 in order, plus the periodic `pg_dump` backup step (research §2) and the step to add the partner's email to the Supabase project team
- [ ] T082 [US5] Provision the Azure Container Apps Consumption environment (`minReplicas: 0`, Consumption workload profile) inside `baby-names-rg` via `az containerapp env create` (research §1's load-bearing config)
- [ ] T083 [US5] Build and push the `api/Dockerfile` image to an Azure Container Registry in `baby-names-rg` via `az acr build`
- [ ] T084 [US5] Apply Alembic migrations (`alembic upgrade head`) against the Supabase database using `secrets/.env`'s `DATABASE_URL`, recording the applied revision (FR-026)
- [ ] T085 [US5] Deploy the Container App from the pushed image via `az containerapp create`, setting the Supabase/DB values from `secrets/.env` as Container App **secrets** (not plain env vars)
- [ ] T086 [US5] Create the daily scheduled Container Apps Job running the `keepalive` entrypoint via `az containerapp job create`, in the same `baby-names-rg` (research §2)
- [ ] T087 [US5] Configure an Azure spend/budget alert on `baby-names-rg` at any nonzero amount via `az consumption budget create` (FR-024)
- [ ] T088 [US5] Follow `api/DEPLOY.md` end to end and confirm a reachable service, migrations applied in order, and zero credentials in the repository at any commit (SC-009)
- [ ] T089 [US5] Confirm the daily keepalive job succeeds on its schedule, pings the database directly rather than through `/health`, and costs roughly 75 vCPU-seconds/month (quickstart.md scenario 12)

**Checkpoint**: All five user stories are independently functional. The full spec is delivered.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Close out documentation and run the full validation pass now that every story is in place.

- [ ] T090 [P] Update `CLAUDE.md`'s Stack & hosting and Data model sections to describe the backend, accounts, and localStorage's demotion to offline cache
- [ ] T091 [P] Update `docs/remaining-items.md` if any deferred item's status changed during implementation
- [ ] T092 Run every scenario in `quickstart.md`'s Validation scenarios end to end and record results
- [ ] T093 Confirm SC-003 — an online session of 500+ names with no repeated name, no empty-deck state, and no visible pause at a block boundary

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. Blocks all user stories — schema, auth, rate limiting, health, and the test harness are shared by every endpoint.
- **User Stories (Phase 3–7)**: All depend on Foundational completion.
  - US1, US2, US3 are all P1 and can proceed in parallel once Foundational is done, though US2 (deck) and US3 (offline sync) both build on US1's client scaffolding (`src/lib/api.ts`, the sign-in gate) — see note below.
  - US4 (dev loop) and US5 (deploy) depend only on Foundational, not on US1–US3, and can start any time after Phase 2 — but validating them (T077–T079, T088–T089) is most meaningful once real endpoints exist to check against.
- **Polish (Phase 8)**: Depends on all five user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. Delivers accounts + state restore.
- **US2 (P1)**: Depends only on Foundational for its backend half (T049–T058). Its client half (T059–T062) touches `src/lib/api.ts`, created in US1 (T041) — sequence US1's client tasks before US2's client tasks if working solo; a second contributor can build the backend half of US2 fully in parallel with US1.
- **US3 (P1)**: Same shape as US2 — backend half (T063–T067) only needs Foundational; client half (T068–T073) builds on `src/lib/api.ts` and the sign-in gate from US1, and on `requestNextBlock` from US2 (T071).
- **US4 (P2)**: Depends only on Foundational's `make check` scaffolding (Phase 1–2). Most valuable once US1–US3 give it real behavior to gate.
- **US5 (P3)**: Depends only on Foundational (`db.py`, `main.py`, migrations) plus the credentials noted at the top of this file. Independent of US1–US4's application logic; T082–T087's `az` provisioning can happen any time after Foundational, though T088's runbook validation is more meaningful once the app has real endpoints to smoke-test.

### Within Each User Story

- Tests are written first and MUST fail before implementation (FR-028).
- Backend: schemas → routers → wiring into `main.py`.
- Frontend: `src/lib/` modules → `src/BabyNameSwipe.tsx` wiring.
- Story complete before moving to the next priority, if working sequentially.

### Parallel Opportunities

- All Setup tasks marked `[P]` (T002–T006, T008) can run together.
- Within Foundational, the six model files (T012–T017) are `[P]`; the test files (T019, T020, T022, T024) are `[P]` against each other and against the models.
- Once Foundational is done, US1, US2's backend half, US3's backend half, US4, and US5 can all proceed in parallel with separate contributors.
- Within a story, all test files marked `[P]` can be written together; within Foundational and US1/US2/US3 implementation, tasks touching different files are `[P]`.

---

## Parallel Example: User Story 1

```bash
# Tests for User Story 1 (different files — run together):
Task: "Contract test: GET /v1/state auth in api/tests/contract/test_state_auth.py"
Task: "Contract test: GET /v1/state shape in api/tests/contract/test_state_get.py"
Task: "Contract test: PUT /v1/settings in api/tests/contract/test_settings_put.py"
Task: "Contract test: POST /v1/reset in api/tests/contract/test_reset.py"
Task: "Integration test: account provisioning in api/tests/integration/test_account_provisioning.py"
Task: "Integration test: state restore (SC-001) in api/tests/integration/test_state_restore.py"

# Client scaffolding for User Story 1 (different files — run together):
Task: "Create src/lib/auth.ts"
Task: "Create src/lib/api.ts"
```

---

## Implementation Strategy

### MVP First (User Stories 1–3)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (blocks everything).
3. Complete Phase 3 (US1), Phase 4 (US2), Phase 5 (US3) — together these are the P1 slice and the actual MVP: a signed-in, offline-capable, synced swiping experience with server-owned names.
4. **STOP and VALIDATE**: run quickstart.md scenarios 1, 3, 4, 5, 6, 7, 8 against the real stack.
5. Hand-deploy (US5) to have something to validate against; layer in US4's dev-loop polish alongside.

### Incremental Delivery

1. Setup + Foundational → schema, auth, rate limiting, health, test harness all exist.
2. Add US1 → sign in and restore state → validate independently.
3. Add US2 → real, correctly-ordered names → validate independently.
4. Add US3 → offline swiping and sync → validate independently (MVP complete).
5. Add US4 → dev loop hardened for unattended use.
6. Add US5 → hand-deploy runbook exercised end to end against the real Azure subscription and Supabase project.
7. Polish → docs updated, full quickstart pass, SC-003 confirmed.

### Parallel Team Strategy

With multiple contributors, after Foundational:

- Contributor A: US1 (accounts/state, both backend and client).
- Contributor B: US2's backend half (deck algorithm, endpoint), then US2's client half once US1's `src/lib/api.ts` lands.
- Contributor C: US5 (deploy runbook, keepalive job, `az` provisioning) — fully independent of US1–US3.
- US3 and US4 pick up once US1's client scaffolding and US2's `requestNextBlock` exist.

---

## Notes

- `[P]` tasks touch different files with no dependency on an incomplete task.
- `[Story]` labels trace every task back to spec.md's user stories for independent testing.
- FR-028 (test-first) applies throughout, including Foundational — auth and rate-limit behavior each have a test written before their implementation task.
- The float64 underflow reproduced in US2 (T049, T055) is deliberate fidelity, not a bug to fix — see research §5 and `docs/remaining-items.md` §2.
- Real Supabase and Azure credentials are never created fresh or requested from the user during implementation — they come from `secrets/.env` and the pre-authenticated `az` CLI/existing `baby-names-rg` resource group on the implementing machine (see "Credentials available on the implementing machine" above).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
- Avoid: vague tasks, same-file conflicts under `[P]`, and cross-story dependencies that break independent testability beyond the noted `src/lib/api.ts` sequencing.
