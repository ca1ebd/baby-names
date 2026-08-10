# Data Model: Backend, Accounts & Sync

**Created**: 2026-08-10 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Six tables. Storage grows with what people actually swipe, not with the size of
the corpus times the number of accounts — that constraint drove most of the
shape below.

## `names` — the corpus (FR-012)

Seeded once from the same generated source the client bundles today, then the
client's copy is deleted.

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | Stable; referenced by picks and served order |
| `name` | `text` | Unique across the whole table, not just per gender |
| `gender` | `text` | `girl` \| `boy` |
| `rank` | `int` | Position within its gender's list. **This is the popularity rank** the deck algorithm exponentiates, and 003 will read it for "common but not top-10" criteria |
| `is_core` | `bool` | `rank < GIRL_CORE_SIZE` (7,457) or `BOY_CORE_SIZE` (5,707) |

**Constraints**: `UNIQUE (name)` — global, not per-gender. This enforces
FR-016's zero-overlap rule at the database level, which matters because picks
are keyed by name and a collision would let a pick in one gender silently
affect the other. `UNIQUE (gender, rank)`.

**Volume**: 63,880 rows, ~2 MB. Immaterial against the free plan's 500 MB.

## `accounts` — one couple (FR-003, FR-007, FR-014)

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | **Is** the Supabase auth user id. No separate user table to keep in sync |
| `deck_seed` | `bigint` | Per-account, assigned at creation. Retires the global `20260730` |
| `last_name` | `text` | May be empty |
| `gender_filter` | `text` | `girl` \| `boy` \| `both` |
| `onboarded` | `bool` | Drives the Welcome screen, as today |
| `created_at` | `timestamptz` | |

## `swipers` — the two people (FR-003, FR-007)

Two rows per account. Merges the labels and the deck positions that FR-013
needs, rather than splitting them across two tables.

| Column | Type | Notes |
|---|---|---|
| `account_id` | `uuid` FK → `accounts` | |
| `slot` | `smallint` | `0` = you, `1` = partner. Matches today's `people[0]`/`people[1]` |
| `label` | `text` | Display name; partner's may be empty |
| `position` | `int` | How far into `served_order` this swiper has gone. The max across both slots is "the furthest swiper" that 003 rebuilds beyond |

**Constraints**: PK `(account_id, slot)`; `slot IN (0, 1)`.

## `served_order` — what was dealt, in order (FR-013)

Append-only. The immutable record that makes both swipers walk the same path
and that 003 rebuilds from beyond the furthest swiper's position.

| Column | Type | Notes |
|---|---|---|
| `account_id` | `uuid` FK → `accounts` | |
| `position` | `int` | 0-based, dense, per account |
| `name_id` | `int` FK → `names` | |

**Constraints**: PK `(account_id, position)`; **`UNIQUE (account_id,
name_id)`** — this is what makes FR-015's "never serve a duplicate" a database
guarantee rather than something application code has to remember. A bug that
tries to re-deal a name fails loudly instead of quietly showing it twice.

**Growth**: one row per name actually dealt. A couple who swipes 5,000 names
has 5,000 rows, not 63,880.

## `picks` — one swiper's verdict on one name (FR-007, FR-009, FR-023)

| Column | Type | Notes |
|---|---|---|
| `account_id` | `uuid` FK → `accounts` | |
| `slot` | `smallint` | |
| `name_id` | `int` FK → `names` | |
| `verdict` | `text` | `keep` \| `no` |
| `decided_at` | `timestamptz` | **Client-supplied.** The tiebreak for last-write-wins convergence |

**Constraints**: PK `(account_id, slot, name_id)`.

The composite PK is what makes sync idempotent (FR-020): a repeated flush is an
upsert onto the same key, so replaying a batch — or interleaving batches from
two devices — converges without coordination. `decided_at` comes from the
device that made the pick rather than from the server, because a pick made
offline on Tuesday and synced on Friday should not outrank one made on
Wednesday.

**Deliberately not modelled**: matches. They stay derived from picks at read
time (FR-009), preserving 001's rule that a swiped name never vanishes from
Matches even if the corpus changes.

## `rate_limit_windows` — abuse protection (FR-032)

| Column | Type | Notes |
|---|---|---|
| `account_id` | `uuid` FK → `accounts` | |
| `window_start` | `timestamptz` | Truncated to the hour |
| `request_count` | `int` | |

**Constraints**: PK `(account_id, window_start)`.

In Postgres rather than in process memory, because Container Apps restarts the
container on every scale-from-zero and may run more than one replica — an
in-memory counter would enforce nothing. One upsert per request. Rows older
than the current window are disposable; the runbook prunes them.

## Client-side cache shape

`babyname-swipe-v3` keeps its key (Constitution IV) and changes its value. It
stops being the system of record and becomes a cache plus an outbox:

```
{
  account:     { id, lastName, genderFilter, onboarded },
  swipers:     [{ label, position }, { label, position }],
  block:       [{ position, name, gender }],   // the dealt, unswiped run
  picks:       { [name]: { slot, verdict, decidedAt } },  // for offline Matches
  outbox:      [{ slot, name, verdict, decidedAt }],      // unsynced, flushed in order
  syncedAt:    timestamp
}
```

The `outbox` is what makes FR-019 and FR-020 work: picks land there
synchronously on every swipe, and a flush deletes only the entries the server
acknowledged. A flush that fails halfway leaves the rest queued, and replaying
an acknowledged entry is harmless because the server upserts.

## Relationships

```
accounts 1─┬─2  swipers          (slot 0, 1)
           ├─n  served_order      (append-only, dense positions)
           ├─n  picks             (slot × name)
           └─n  rate_limit_windows

names    1─┬─n  served_order
           └─n  picks
```

## State transitions

**Account**: created on first sign-in (`onboarded: false`) → Welcome completed
(`onboarded: true`). "Reset everything" returns it to `onboarded: false` and
clears `picks`, `served_order`, and `swipers.position` — a reset is a reset
everywhere, per the spec's edge case, and the confirmation dialog says so.

**Pick**: absent → `keep`/`no`, and freely re-decidable (undo, or the same name
re-swiped on another device). Convergence is last-`decided_at`-wins.

**Served order**: append-only within this feature. It has exactly one mutation
path, added by 003: rebuild the tail beyond `max(swipers.position)`. Positions
at or below that mark are permanently frozen — which is the guarantee that
makes matching trustworthy once the deck can change.
