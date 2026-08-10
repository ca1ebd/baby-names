# Research Notes: Backend, Accounts & Sync

**Created**: 2026-08-10
**Purpose**: Resolve the unknowns in the plan's Technical Context before design.

Five questions had to be answered before this feature could be designed
honestly. Three of them changed the plan; one of them nearly invalidates the
$0 cost posture and is the most important thing in this document.

---

## 1. Is $0/month actually achievable on Azure Container Apps?

**Decision**: Yes, on a **Consumption-only** environment with `minReplicas: 0`.

Azure Container Apps' Consumption plan grants the first **180,000 vCPU-seconds,
360,000 GiB-seconds, and 2 million requests per subscription per month free**,
and an app scaled to zero incurs no usage charges at all.

At the smallest practical replica size (0.25 vCPU / 0.5 GiB), the free grant
covers roughly **200 hours of active container time per month**. A two-person
app that wakes for a few minutes a day uses a tiny fraction of that. Request
volume is nowhere near 2M.

**Two configuration details are load-bearing and must not drift**:

- The environment must use the **Consumption** workload profile. A Dedicated
  workload profile bills for the profile itself whether or not anything runs,
  which would break FR-024 silently.
- `minReplicas` must be **0**. Setting it to 1 to dodge cold starts moves the
  app onto idle rates and starts a meter — it is exactly the tempting change
  that would quietly turn a $0 bill into a monthly charge.

**Alternatives considered**: Azure App Service Free (F1) tier — no container
support in the way this needs, and 60 min/day CPU quota. Azure Functions
Consumption — a better raw fit for scale-to-zero, but the spec mandates a
container on Container Apps, and Functions would fight the FastAPI structure.

**Consequence**: cold start is real and must be designed around, not wished
away. That is what FR-030's warm-up exists for.

---

## 2. Will the free Supabase database stay alive? *(this one bites)*

**Decision**: Not on its own. A scheduled keep-alive is **mandatory**, not an
optimization.

Free-plan Supabase projects **pause after 7 days without sufficient database
activity**. A paused project is unreachable until someone restores it, and
restoring is a **manual click in the dashboard** — there is no automatic
wake-on-request. Worse, Supabase **permanently deletes** free projects that
stay paused for an extended period.

This is a materially worse failure mode than the cold start in §1, and the spec
already flagged it as needing a plan-time answer (see the "Free-tier database
suspended after prolonged inactivity" edge case). The answer:

- **A scheduled daily ping** against `GET /health`, which touches the database
  (`SELECT 1`), keeps the 7-day clock from ever starting. A GitHub Actions
  `schedule:` workflow does this for free.
- **This is not CI/CD** and does not breach the spec's deferral of it. It
  builds nothing and deploys nothing; it is a liveness heartbeat. Calling it
  out explicitly so the next spec's scope stays clean.
- **Caveat to document in the runbook**: GitHub disables scheduled workflows in
  repositories with no activity for 60 days. A repo that goes quiet for two
  months loses its heartbeat, and seven days later the database pauses. The
  runbook must say so.
- **Backups**: because permanent deletion is on the table, the manual deploy
  runbook must include a periodic `pg_dump`. The app's existing Copy Backup
  feature covers a couple's own picks but not the account or corpus tables.

**Alternatives considered**: relying on organic traffic (two users on parental
leave will not reliably hit it every week); a paid plan (violates FR-024);
`pg_cron` inside Supabase (does not count as *user* activity for the pause
heuristic, so it does not help).

---

## 3. How does the backend verify a Supabase-issued session?

**Decision**: Verify the JWT locally against Supabase's **JWKS endpoint**,
using asymmetric signing keys. No call to Supabase per request.

Supabase publishes public keys at `https://<project-ref>.supabase.co/auth/v1/
.well-known/jwks.json` (edge-cached ~10 minutes). Tokens carry a `kid` header
identifying which key signed them. The backend fetches the JWKS once, caches
it, and verifies signatures offline — which matters here because a
scaled-to-zero service should not add a network round-trip to every request.

Key rotation is handled by Supabase's key states (Active / Standby / Previously
used / Revoked); a backend that re-fetches JWKS on an unknown `kid` survives
rotation without a deploy.

**Alternatives considered**: the legacy shared HS256 secret — simpler, but it
is the deprecated path and puts a symmetric secret in the container's
environment. Calling Supabase's `/auth/v1/user` per request — correct but adds
latency and a hard dependency on Supabase being up for every single request.

---

## 4. Can magic-link auth actually send email on the free tier? *(no)*

**Decision**: A **custom SMTP provider is required**. Supabase's built-in email
sender cannot be used for this feature.

Supabase's built-in auth email service is capped at **2 emails per hour** and —
decisively — **only delivers to addresses belonging to the project's team**. It
is explicitly a testing facility, not a production sender.

For a feature whose entire sign-in flow is "we email you a link," that is a
blocker, not an inconvenience. Two failed sign-in attempts would lock a user
out for an hour, and nobody outside the project team could ever create an
account.

**What this means**: FR-002 (passwordless magic link) carries an implicit
dependency the spec did not name — a third-party email sender. It must be on a
free tier to satisfy FR-024. Resend's free allowance (on the order of thousands
of emails/month) is far beyond what a two-person app needs, and Brevo and
Mailgun have comparable free tiers. Any of them satisfies the constraint;
the choice is a runbook detail, not an architectural one.

With custom SMTP configured, Supabase's own auth rate limit rises to ~30 new
users/hour, which is irrelevant at this scale.

**This is a new external dependency and the owner should know about it.** It
does not change the answer to the clarification (magic link is still the least
work overall), but "no passwords to handle" now comes with "an SMTP account to
configure and keep alive."

---

## 5. How is per-account deck order reproduced server-side?

**Decision**: Reproduce the frontend's float64 semantics **exactly**, in
Python, seeded per account — including the underflow behavior described below.
Do not "fix" the algorithm.

### The finding

The frontend's `weightedShuffle` gives each name `key = u^(rank+1)` where `u`
comes from a seeded LCG, then sorts by key descending. Measured against the
real core size (7,457 girl names):

| Measurement | Value |
|---|---|
| Keys that underflow to exactly `0.0` | **5,339 of 7,457 (71.6%)** |
| First rank to underflow | **230** |
| Median rank of the first 20 cards | 234 (matches the documented ~180 target within sampling noise) |
| Dealt position after which order is strict rank | **~2,118** |

`u^(rank+1)` falls below float64's smallest subnormal well before rank 7,457 —
for a typical `u ≈ 0.5`, that happens around rank 1,075. Every underflowed name
has key `0.0`, and because `Array.prototype.sort` is **stable**, they retain
their original relative order. So the deck's real behavior is:

1. Roughly the first ~2,100 dealt cards are genuinely popularity-weighted.
2. Everything after that is **strict rank order**, not a shuffle.
3. Then the flat-shuffled tail.

This is not documented anywhere, including `CLAUDE.md`, and it is almost
certainly not what the original tuning intended past card ~2,100. But it *is*
what every existing deck does.

### Why reproduce rather than fix

A log-space implementation (`(rank+1) * ln(u)`, mathematically equivalent,
numerically stable) would genuinely shuffle the deep core — changing what a
user sees from card ~2,100 onward. SC-004's 500-card test would not catch it.
Since this feature's whole premise is "a couple notices nothing except signing
in" (FR-008), silently changing the deck past card 2,100 is out of scope, and
doing it accidentally would be worse.

**Implementation requirement**: sort by `(key DESC, rank ASC)` so the stable
tie-break that JavaScript provided implicitly is explicit and portable. Python's
`sorted` is also stable, so a faithful port is straightforward; the explicit
tie-break exists so the behavior survives a move into SQL later.

**Recorded for a future spec**: whether the deep core *should* be shuffled is a
real product question. It is deliberately not answered here.

### Where the computation runs

In **Python at block-deal time**, not in SQL and not on the client. Running the
7,457-element weighted shuffle takes on the order of milliseconds, happens only
when a block is dealt, and keeps the exact float64 semantics that SQL's numeric
handling would put at risk. The dealt names are then appended to `served_order`,
so the record of what was served is authoritative and immutable even if the
algorithm is ever changed.

**Alternatives considered**: materializing all 63,880 positions per account at
signup (wastes storage proportional to accounts × corpus for names nobody will
reach); computing order in SQL via a hash-based `u` (loses exact fidelity with
the frontend and changes every deck); a global order permuted per account by a
bijection (destroys the popularity weighting entirely).

---

## 6. Library-level choices (established practice, low risk)

Settled by convention rather than research; recorded so the plan is explicit.

- **Sync SQLAlchemy 2.0 + psycopg 3**, not async. Supabase's transaction-mode
  pooler does not support prepared statements, which asyncpg uses by default —
  a well-known footgun requiring `statement_cache_size=0`. At this concurrency
  (two users), async buys nothing, and sync keeps Alembic, testcontainers, and
  pyright-strict all straightforward. FastAPI runs sync endpoints in a
  threadpool.
- **Declarative `Mapped[...]` / `mapped_column()`** typing throughout, which is
  what makes SQLAlchemy 2.0 legible to pyright in strict mode.
- **testcontainers-python** with a session-scoped `PostgresContainer`, Alembic
  `upgrade head` once, then a per-test transaction rolled back. Fast enough to
  keep `make check` under the SC-008 five-minute budget.
- **Rate limiting in Postgres**, not in process memory. Container Apps can run
  multiple replicas and restarts on every scale-from-zero, so an in-memory
  counter enforces nothing. A fixed-window row per (account, hour) is one
  upsert per request and costs nothing.

## Sources

- [Azure Container Apps pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/)
- [Billing in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/billing)
- [Supabase: Project Pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
- [Supabase Pricing](https://supabase.com/pricing)
- [Supabase: JSON Web Tokens](https://supabase.com/docs/guides/auth/jwts)
- [Supabase: JWT Signing Keys](https://supabase.com/docs/guides/auth/signing-keys)
- [Supabase: Send emails with custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp)
- [Supabase: Production Checklist](https://supabase.com/docs/guides/deployment/going-into-prod)
