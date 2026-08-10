# Contract: HTTP API

**Created**: 2026-08-10 | **Plan**: [plan.md](plan.md) | **Data model**: [data-model.md](data-model.md)

Six endpoints. All paths are versioned under `/v1` except `/health`, which is
deliberately unversioned because the keep-alive workflow and the client warm-up
both hit it and neither should ever have to care about a version bump.

## Conventions

**Authentication**: every `/v1` endpoint requires `Authorization: Bearer
<supabase-jwt>`. The token is verified offline against cached JWKS; the `sub`
claim is the account id. A missing, malformed, expired, or unverifiable token
returns `401`. There is no anonymous access to anything under `/v1` (FR-001).

**Account provisioning**: the first authenticated request from an unknown but
valid `sub` creates the account row, its two swipers, and its `deck_seed`. There
is no separate signup endpoint — Supabase already owns that half.

**Errors**: `{"error": {"code": "...", "message": "..."}}`. Codes the client
branches on: `rate_limited`, `unauthenticated`, `corpus_exhausted`. Everything
else the client renders as the single friendly waiting state (FR-031).

**Rate limiting** (FR-032): a per-account fixed hourly window. Over-limit
requests return `429` with `Retry-After`. The client shows the waiting state,
never an error, and never discards a queued pick because of a `429`.

---

## `GET /health`

Unauthenticated. Liveness plus the warm-up target (FR-029, FR-030).

**Must touch the database** (`SELECT 1`), not just return a constant — that is
what makes it useful as both a real health signal and the keep-alive that stops
the free project from pausing (research §2).

**200**
```json
{ "status": "ok", "database": "ok", "version": "<commit-sha>" }
```
**503** — `{"status": "degraded", "database": "unreachable"}` when the app is up
but the database is not, which is the distinction that makes a broken deploy
visible without reading logs.

---

## `GET /v1/state`

Everything needed to restore a signed-in user on a fresh device (FR-007, US1).

**200**
```json
{
  "account":  { "lastName": "Dudley", "genderFilter": "girl", "onboarded": true },
  "swipers":  [ { "slot": 0, "label": "Caleb", "position": 412 },
                { "slot": 1, "label": "Partner", "position": 380 } ],
  "picks":    [ { "slot": 0, "name": "Nora", "verdict": "keep",
                  "decidedAt": "2026-08-09T18:04:11Z" } ]
}
```

Picks are returned in full rather than paged. A couple who has swiped 5,000
names transfers a few hundred KB once per fresh sign-in; paging this would add
a state machine to the client for no benefit at any plausible scale. If that
ever stops being true, the fix is a cursor here, not a change to the model.

Names are returned as strings, not ids — the client keys picks by name (001),
and shipping ids would force it to hold a name table it no longer has.

---

## `PUT /v1/settings`

Auto-saved from the Settings screen on the existing ~400 ms debounce. The
screen's behavior is unchanged (FR-008).

**Request**
```json
{ "lastName": "Dudley", "genderFilter": "both", "onboarded": true,
  "swipers": [ { "slot": 0, "label": "Caleb" }, { "slot": 1, "label": "Sam" } ] }
```
**200** — the updated `account` and `swipers` objects.

Changing `genderFilter` does **not** rewrite `served_order`. Already-dealt
names keep their positions; the filter applies to names dealt from here on.
Rewriting history on a filter change would break the same guarantee 003 depends
on, for a setting the user may toggle back a second later.

---

## `POST /v1/deck/next`

Deal the next run of names for a swiper (FR-013, FR-014, FR-017, FR-021).

**Request** — `{ "slot": 0, "count": 100 }` (`count` clamped to 1–200)

**200**
```json
{ "block": [ { "position": 412, "name": "Nora",  "gender": "girl" },
             { "position": 413, "name": "Wren",  "gender": "girl" } ],
  "exhausted": false }
```

Behavior:
- Returns names from `position` = the swiper's current position onward.
- If the requested run extends past the end of `served_order`, the service
  deals more first: run the account-seeded weighted shuffle, skip anything
  already served, append, then return. Appending is what makes the trailing
  swiper replay exactly what the leading swiper saw.
- `exhausted: true` with a short or empty block means the corpus is genuinely
  used up for this filter (FR-017) — the client says so plainly rather than
  showing an empty deck.
- Dealing is idempotent under concurrent calls: the `UNIQUE (account_id,
  name_id)` constraint means a racing second call cannot double-deal.

---

## `POST /v1/picks`

Flush the offline outbox (FR-019, FR-020, FR-023).

**Request**
```json
{ "picks": [ { "slot": 0, "name": "Nora", "verdict": "keep",
               "decidedAt": "2026-08-09T18:04:11Z" } ] }
```
**200** — `{ "accepted": 37, "swipers": [ { "slot": 0, "position": 449 } ] }`

Behavior:
- **Idempotent by construction**: upsert on `(account_id, slot, name_id)`,
  keeping the row with the later `decidedAt`. Replaying a batch, or sending
  overlapping batches from two devices, converges on the same state — which is
  what SC-005's interrupt-and-retry test exercises.
- `decidedAt` is client-supplied on purpose (see data-model.md): a pick made
  offline on Tuesday and synced Friday must not outrank one made Wednesday.
- Accepts picks for names not in the swiper's current block, so a device that
  fell behind can still flush.
- Batches are capped (suggested 500) so a long offline session flushes in
  several requests rather than one that might time out mid-write.
- The response echoes recomputed swiper positions so the client does not have
  to guess whether its local position survived the merge.

---

## `POST /v1/reset`

**Request** — `{ "scope": "everything" }` or `{ "scope": "swiper", "slot": 0 }`

**200** — the same body as `GET /v1/state`, post-reset.

`everything` clears picks, served order, and both positions, and sets
`onboarded: false` — matching the existing "RESET EVERYTHING ON THIS DEVICE"
button, whose label and confirmation copy must change since it is no longer
device-scoped. `swiper` clears one slot's picks and resets its position,
matching "START [NAME] OVER". Neither deletes the account.

---

## Client obligations

Not enforceable by the server, but part of the contract:

1. **Warm up on load** (FR-030): `GET /health` fires as soon as the app boots,
   before sign-in and before anything the user waits on, so the cold start
   overlaps with the sign-in screen. Failure is silent.
2. **Refill early** (FR-021): request the next block at a low-water mark
   (suggested 20 remaining), never at exhaustion.
3. **Queue then flush** (FR-019): every swipe lands in the local outbox
   synchronously. Flush on reconnect, on block request, and on sign-out. Delete
   only acknowledged entries.
4. **One waiting state** (FR-031): offline, waking, `429`, and `5xx` all render
   the same friendly message. A raw error is a bug.
5. **Clear on sign-out** (FR-006): attempt a flush, then drop the cached block
   and picks so the next person on a shared device sees nothing.
