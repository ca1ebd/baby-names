# Quickstart & Validation: Backend, Accounts & Sync

**Created**: 2026-08-10 | **Plan**: [plan.md](plan.md) | **Contract**: [contracts/http-api.md](contracts/http-api.md)

How to run the service, and the scenarios that prove the feature works. Each
scenario names the requirement and success criterion it validates, so a green
run here is evidence against the spec rather than a vibe.

## Prerequisites

- Python 3.12, Docker (for testcontainers), Node 20+ for the client
- A Supabase project (free plan). This release uses the **built-in** auth email
  sender, so **both users' email addresses must be added to the project team** —
  it refuses to deliver anywhere else, and it caps at 2 messages/hour. Real SMTP
  is deferred; see [docs/remaining-items.md](../../docs/remaining-items.md).
  Never exercise real email delivery from tests: backend tests mint JWTs
  directly, and local work uses the Supabase CLI's mail catcher.
- No local Postgres needed. `make check` provisions and disposes its own.

## Environment

Never committed (FR-025). `api/.env.example` documents the shape; real values
come from the local file or the Container App's secrets.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Supabase Postgres, **transaction pooler** (port 6543) |
| `SUPABASE_PROJECT_REF` | Derives the JWKS URL for offline token verification |
| `CORS_ORIGINS` | The two frontend origins (prod, staging) |
| `RATE_LIMIT_PER_HOUR` | Default 1000 — ~2 orders of magnitude above real use |
| `VITE_API_BASE_URL` | Client → service (frontend build) |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | Client auth (publishable) |

## The gate

```bash
make check          # ruff + pyright --strict + pytest on a throwaway Postgres
```

One command, one pass/fail, no manual setup, nothing shared or left running
(FR-027, SC-008). This is what the agent runs after every edit and what it must
get green before surfacing a diff.

```bash
make check-web      # oxlint + tsc + vite build (frontend)
make dev            # service on :8000 against a local container
make migrate        # alembic upgrade head
make seed-corpus    # load the 63,880 names — idempotent, safe to re-run
```

Expected first run: a few minutes while the Postgres image pulls; steady-state
well under the five-minute budget.

## Working test-first (FR-028)

Every change starts as a failing test that describes the intended behavior.
The loop is: write the test, watch it fail *for the right reason*, implement the
smallest thing that passes, re-run `make check`, fix your own fallout, then
surface the diff. A test that passes the moment you write it has not described
anything.

---

## Validation scenarios

### 1. Sign in and your state follows you — US1, SC-001

1. Sign in with a new email; complete Welcome; swipe ~30 names.
2. Open a fresh browser profile and sign in as the same account.
3. **Expect**: identical picks, matches, labels, last name, gender filter.
   First card within 3 s of completing sign-in.
4. Sign out and back in. **Expect**: nothing lost, no return to onboarding.

### 2. Sign-in is limited to authorized addresses — FR-002, research §4

Attempt sign-in with an address **not** on the Supabase project team.
**Expect**: no magic link is ever delivered. This is the deferred-SMTP limit
working as designed, not a bug — but it is the first thing to check when
sign-in "doesn't work" for someone. Confirm the app's copy does not promise
anything it cannot deliver here.

### 3. No anonymous access — US1 scenario 2, FR-001

Open the app signed out. **Expect**: a sign-in prompt, and no deck, picks, or
settings reachable. Then call any `/v1` endpoint with no token and with a
token from a *different* account. **Expect**: `401`, and no cross-account read
or write (SC-006 — this must be a test, not an inspection).

### 4. A full block offline — US3, SC-002

1. Sign in, let a block load, then go offline (DevTools, or airplane mode).
2. Swipe the entire block. **Expect**: every card advances, undo works, Matches
   updates, no error state, no perceptible delay.
3. Reconnect without touching the app. **Expect**: every pick reaches the
   account within 10 s, no duplicates.
4. Keep swiping offline past the end of the block. **Expect**: the friendly
   "more names when you're back online" state, all picks intact, and automatic
   resumption on reconnect.

### 5. Sync survives interruption — SC-005

Kill the connection at 20 randomized points mid-flush, then retry. **Expect**:
final state identical to one clean sync every time — no duplicated, dropped, or
reordered picks. This is the highest-value test in the suite; the composite
primary key on `picks` is what makes it pass, so if it ever fails, suspect the
upsert before suspecting the client.

### 6. Both swipers walk the same path — US2 scenario 5, SC-004

Swipe 150 names as slot 0, then switch to slot 1. **Expect**: slot 1 is served
the *same* names in the *same* order. Then sign the same account in on a second
device and confirm both agree.

### 7. Each account gets its own deck — US2 scenario 6, SC-004

Create two accounts with the same gender filter. **Expect**: visibly different
orders, and each account's own order reproducible across repeated runs. A shared
order here means the per-account seed is not being applied.

### 8. Deck ordering is faithful to the current app — FR-014, US2 scenario 4

A unit test must assert the port matches the frontend algorithm **exactly**,
including the float64 underflow documented in research §5:

- ~71.6% of the 7,457-name girl core produces key `0.0`, first at rank 230
- sorting is stable, so dealt positions past ~2,118 come out in strict rank order
- the median rank of the first 20 cards sits near 180–235

If a change makes the deep core genuinely shuffled, this test must fail. That
behavior is odd, but it is what every existing deck does, and quietly changing
it would violate the parity premise this whole feature rests on.

### 9. Rate cap protects the free tier — SC-012, FR-032

Drive a client past `RATE_LIMIT_PER_HOUR`. **Expect**: `429` with `Retry-After`,
the friendly waiting state in the UI, and no queued pick lost. Then simulate an
hour of continuous human swiping. **Expect**: never trips.

### 10. Cold start is invisible — FR-030, SC-001

Leave the service idle until it scales to zero. Open the app and time from first
paint to first card. **Expect**: the warm-up absorbs the cold start during
sign-in; a returning user with a live session sees the waiting state rather than
an error if the container is still coming up.

### 11. Deploy from the runbook — US5, SC-009, SC-010

Follow `api/DEPLOY.md` end to end on a clean environment. **Expect**: a
reachable service, migrations applied in order, and **zero credentials in the
repository at any commit**. Someone who has not deployed it before should
succeed from the document alone — that is the actual test.

### 12. The database is still there next month — research §2

Confirm the daily keep-alive Container Apps job is scheduled and its recent
executions succeeded. **Expect**: one successful run per day, each completing in
seconds.

This one matters more than it looks. A free Supabase project pauses after 7 days
of inactivity, needs a **manual dashboard click** to restore, and is
**permanently deleted** if left paused. The heartbeat is not an optimization —
it is what stops the database from being deleted during a quiet month.

Two things to verify deliberately, because both failure modes are silent:

- **The job pings the database directly**, not through `GET /health`. Confirm a
  deliberately broken HTTP app does not stop the heartbeat — otherwise an
  application bug becomes data loss on a seven-day fuse.
- **Daily, not weekly.** Supabase's threshold is a few requests a day across the
  previous week, so a weekly cadence has no margin for a single failed run.

Cost check while you are here: the job should draw roughly 75 vCPU-seconds a
month against the 180,000-second free grant. If it is materially more, something
is running longer than it should.

---

## Bundle check — SC-011

After `nameCorpus.ts` is deleted, compare gzip size against `main`. **Expect**:
roughly 217 KB smaller, and cold load no slower than today's.
