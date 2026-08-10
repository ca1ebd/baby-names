# Feature Specification: Backend, Accounts & Sync

**Feature Branch**: `backend-accounts-sync`

**Created**: 2026-08-10

**Status**: Draft — 2 open clarifications

**Depends on**: [001-expanded-name-corpus](../001-expanded-name-corpus/spec.md)
— the name corpus this feature moves off-device and serves from the backend.

**Blocks**: [003-ai-name-filter](../003-ai-name-filter/spec.md) — criteria
filtering was originally 002 and was renumbered on 2026-08-10 when the owner
judged that building it on purely local state was the cart before the horse.
The served-order record that 003 assumed it would have to invent is now this
spec's plumbing (User Story 3, FR-011/FR-012).

**Input**: User description: "I realized we've put the cart before the horse a
bit the AI stuff in spec 2, make that spec 3. Instead of everything being
local, I want to move the state of app into the backend. So that means the
global names list and the user's state (should be able to be offline until
current block of names runs out, then sync back to backend). A Python 3.12
FastAPI service with Pydantic v2 models and full type annotations, checked by
pyright in strict mode, talking to Postgres through SQLAlchemy 2.0 with Alembic
migrations. It's packaged as a container and deployed to Azure Container Apps,
with Supabase-hosted Postgres behind it. Development is test-first: each change
starts as a failing pytest case describing intended behavior, and
implementation is written only to make it pass. A single make check runs ruff,
pyright, and pytest against a throwaway Postgres via testcontainers, and the
agent runs it after every edit and fixes its own failures before surfacing a
diff. We also need auth/accounts... whatever is easiest there honestly if
supabase has it built in then we'll use that, we don't need anything fancy.

So the goal of this spec is to lay out the plumbing, get feature parity with
what we have now but accounts (not for partners yet/linked yet), and a local AI
dev loop/tooling. For now, no CI/CD, just deploy by hand with API keys until we
get everything working and we'll do CI/CD as the next spec"

## Scope statement

This feature is a **migration, not a new user-facing capability**. Its success
condition is that a couple using the app notices almost nothing except that
they now sign in, and that their swipes survive losing their phone. Everything
the app does today — the deck, the segmented swiper control, matches, settings,
backup/restore, the update toast — must still work identically afterward.

Three things are explicitly **out of scope** and belong to later specs:

- **Partner linking.** One account holds both swipers, exactly as one browser
  does today. Two people with two accounts sharing a deck is a later feature.
- **CI/CD.** This release deploys by hand. Automating it is the next spec.
- **Criteria filtering.** That is [003](../003-ai-name-filter/spec.md), which
  builds on the plumbing this spec lays down.

## Owner-mandated technical constraints

Normally a spec stays clear of implementation. The owner specified a stack
directly, so it is recorded here verbatim as a **constraint on planning**
rather than a decision the plan phase may revisit. The requirements and success
criteria below remain technology-agnostic and testable on their own terms.

- Service: Python 3.12, FastAPI, Pydantic v2, full type annotations, `pyright`
  in strict mode.
- Data: PostgreSQL via SQLAlchemy 2.0, schema evolution through Alembic
  migrations.
- Packaging & hosting: container image deployed to Azure Container Apps;
  Postgres hosted by Supabase.
- Auth: whatever Supabase provides out of the box, preferring the least work.
  Nothing bespoke.
- Development method: **test-first**. Every change begins as a failing pytest
  case that describes the intended behavior; implementation exists only to turn
  it green.
- Developer/agent loop: a single `make check` runs `ruff`, `pyright`, and
  `pytest` against a throwaway Postgres provisioned by testcontainers. The
  agent runs it after every edit and fixes its own failures before surfacing a
  diff.
- Deployment: by hand, with API keys, for this release only.

## Constitution impact

Flagged here so the plan phase's gate has no surprises. Two principles are
directly implicated and one is load-bearing throughout:

- **Principle II (Cost Consciousness)** — the constitution states that
  introducing any server-side component "is a constitutional cost question and
  requires explicit approval." This spec is that request. A monthly ceiling is
  still unset ([NEEDS CLARIFICATION] Q2 below); FR-024 and SC-008 depend on it.
- **Principle III (Pipeline-Only Deployments)** — as written, this principle
  prohibits manual deploys to production. The owner has chosen hand deploys for
  this release, with CI/CD to follow in the next spec. **This is a real
  conflict, not a gray area.** The plan phase must resolve it one of two ways:
  amend the constitution to scope Principle III to the frontend until backend
  CI/CD lands, or record a time-boxed, explicitly justified deviation in the
  plan's Complexity Tracking with the next spec as its expiry. It must not be
  resolved by silence.
- **Principle IV (Storage Key Stability)** — `babyname-swipe-v3` remains the
  on-device key and MUST NOT be renamed. It stops being the only copy of a
  couple's history but keeps working as the offline cache and as the source for
  the one-time import (User Story 4). No user may be forced back through
  onboarding, and no pick may be discarded, by any part of this migration.
- **Principle I (Muted Visual Design)** — the new sign-in surface is the first
  screen a user sees, and it follows the app's existing muted language, minimal
  motion, and mobile input conventions (`fontSize: 16`, safe-area insets,
  `minWidth: 0` on flex children).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Your swipes belong to you, not to a browser (Priority: P1)

A parent creates an account and signs in. Everything the app knows about them —
both swipers' names, the last name, the girl/boy/both filter, and every pick
either of them has made — is stored in their account. Signing in from a
different browser, a reinstalled app, or a replacement phone brings all of it
back exactly as it was.

**Why this priority**: This is the whole point of the migration. Today a
cleared browser cache is unrecoverable data loss for a couple who may have
swiped thousands of names.

**Independent Test**: Sign in, swipe a distinctive set of names, sign in as the
same account in a fresh browser profile, and verify the picks, matches,
profile names, and gender filter all match.

**Acceptance Scenarios**:

1. **Given** a new visitor, **When** they create an account and complete the
   existing Welcome flow, **Then** their profile and settings persist to their
   account and the swipe screen behaves exactly as it does today.
2. **Given** a signed-in user with picks recorded, **When** they sign in on a
   different device or browser, **Then** every pick, match, profile name, last
   name, and the gender filter are restored identically.
3. **Given** a signed-in user, **When** they sign out and back in, **Then** no
   state is lost and they are not sent back through onboarding.
4. **Given** two different accounts, **When** either signs in, **Then** neither
   can see or affect any part of the other's names, picks, or settings.
5. **Given** a signed-in session, **When** the app is reopened days later,
   **Then** the session is still valid and the user is not asked to sign in
   again for routine use.

---

### User Story 2 - The name list comes from the service (Priority: P1)

The global name corpus moves off the device. The app asks the service for a
block of names and deals them to whoever is swiping. Deck quality is unchanged:
the same familiar-first ordering, the same girl/boy/both behavior, the same
per-card color band.

**Why this priority**: Server-owned names are what make every later feature
possible — criteria filtering, partner linking, corpus updates without shipping
a new bundle. It also removes roughly 217 KB gzip from the frontend bundle.

**Independent Test**: With the frontend's bundled corpus removed, load the app
and verify the first cards are real names in a sensible familiar-first order,
correctly gendered, honoring the active filter.

**Acceptance Scenarios**:

1. **Given** a signed-in user on the swipe screen, **When** the deck loads,
   **Then** names are served by the backend and presented exactly as cards are
   presented today.
2. **Given** the gender filter is "girl" or "boy", **When** names are served,
   **Then** only names of that gender appear; **Given** "both", **Then** the
   card band uses the neutral tone as it does today.
3. **Given** any two names served to the same account, **Then** they are never
   the same name — no name is served twice.
4. **Given** the first twenty cards of a fresh deck, **Then** their popularity
   distribution matches today's tuned behavior — the median sits near rank 180
   with roughly one card in six drawn from deeper.
5. **Given** the same account swiping on two devices, **Then** both are served
   the same names in the same order.

---

### User Story 3 - Swipe a whole block with no signal (Priority: P1)

A parent swiping on a commute goes into a tunnel. Swiping keeps working
normally through every name already loaded. Their picks are held on the device.
When the block runs out — or connectivity returns, whichever comes first — the
held picks sync to the service and the next block arrives.

**Why this priority**: Phones lose signal constantly and this app is used in
short bursts on the move. A backend that turns a subway ride into an error
screen is worse than the local-only app it replaced.

**Independent Test**: Load a block, disable the network, swipe the entire
block, re-enable the network, and verify every pick reached the service in the
right order with no duplicates and no losses.

**Acceptance Scenarios**:

1. **Given** a loaded block and no connectivity, **When** the user swipes,
   **Then** every card advances, undo works, and matches update — with no error
   state and no perceptible delay.
2. **Given** picks recorded offline, **When** connectivity returns, **Then**
   they sync to the account without user action and without duplication.
3. **Given** the block is running low and the device is online, **When** the
   user keeps swiping, **Then** the next block arrives before they reach the
   end, with no visible interruption.
4. **Given** the block is exhausted and the device is offline, **When** the
   user tries to continue, **Then** the app shows a friendly "more names when
   you're back online" message, all picks and matches remain intact, and
   swiping resumes automatically once connectivity returns.
5. **Given** a sync that fails or is interrupted midway, **When** it is
   retried, **Then** the result is identical to a single clean sync — no
   duplicated, dropped, or reordered picks.

---

### User Story 4 - Nobody loses what they already swiped (Priority: P1)

A couple who has been using the app locally for months opens it after this
release, creates an account, and finds every name they had already swiped
already there — same picks, same matches, same settings.

**Why this priority**: Constitution IV exists because the browser's copy is
currently the only copy. The moment accounts arrive is the single most
dangerous moment in this app's history for user data, and it happens exactly
once per user.

**Independent Test**: Seed a browser with a realistic pre-migration save, run
the new build, create an account, and verify a 100% match on picks, profile
names, last name, and gender filter — then repeat the sign-in and verify
nothing is imported twice.

**Acceptance Scenarios**:

1. **Given** existing on-device state, **When** the user first signs in,
   **Then** all of it is imported into the account exactly once.
2. **Given** an import has already happened, **When** the user signs in again
   from the same device, **Then** nothing is re-imported and no pick is
   duplicated or reverted.
3. **Given** an import that fails partway, **When** it is retried, **Then** it
   completes without duplicating what already landed, and the on-device copy is
   left intact until the import is confirmed.
4. **Given** a legacy save predating the profiles/gender-filter fields,
   **When** it is imported, **Then** today's backfill defaults apply and the
   user is not forced back through onboarding.

---

### User Story 5 - A dev loop the agent can run unattended (Priority: P2)

A developer — or the coding agent — clones the repository, runs one command,
and gets a full verification pass: linting, strict type checking, and tests
against a real throwaway database. Every change starts life as a failing test.
The agent runs the same command after each edit and fixes what it broke before
showing a diff.

**Why this priority**: This is what makes a hand-deployed backend safe to work
on without CI. Until CI/CD lands in the next spec, `make check` is the only
gate between a change and production.

**Independent Test**: On a clean clone with no database running, `make check`
provisions its own throwaway Postgres, runs all three tools, and reports a
single pass/fail. Deliberately break a type and a test, and confirm it fails
for both reasons with actionable output.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** `make check` runs, **Then** lint, type
   check, and tests all execute against a disposable database and report one
   overall result, with no manual setup and no shared local database required.
2. **Given** a change that breaks types or tests, **When** `make check` runs,
   **Then** it fails and names what broke.
3. **Given** a completed run, **Then** the throwaway database is disposed of
   and nothing persists between runs.
4. **Given** any new behavior in this feature, **Then** a test describing it
   exists and demonstrably failed before the implementation that satisfies it.

---

### User Story 6 - Hand-deploy the service (Priority: P3)

The owner builds the container, pushes it, and rolls out a new backend version
by hand with API keys held outside the repository. Database schema changes are
applied as versioned migrations, in order, with a known state before and after.

**Why this priority**: Deliberately minimal — a documented, repeatable manual
path is enough for this release, and automating it is the next spec's job. It
is P3 because nothing user-facing depends on it beyond the service existing.

**Independent Test**: Follow the written deploy runbook from scratch on a clean
environment and reach a working service, with no credential present in the
repository at any point.

**Acceptance Scenarios**:

1. **Given** the runbook, **When** it is followed step by step, **Then** a
   working service is reachable by the frontend.
2. **Given** a schema change, **When** the deploy runs, **Then** migrations
   apply in order and the version is recorded.
3. **Given** the repository at any commit, **Then** it contains no API key,
   connection string, or other credential.

---

### Edge Cases

- **Signed in on two devices at once**: both are the same account with the same
  two swipers. Picks are keyed by name, so the same swipe from two devices is
  the same fact; the served order is owned by the service, not by either
  device. The last write for a given (swiper, name) wins, and neither device
  ends up with a hole in its history.
- **Session expires mid-swipe**: swiping continues through the loaded block.
  Re-authentication is requested at the next sync, and nothing swiped in the
  meantime is lost.
- **Service unreachable at first ever launch**: a brand-new user with no cached
  block has no names to show. They get a friendly explanation rather than an
  error, and the app recovers on its own when the service returns.
- **Service unreachable for a returning user**: the cached block, matches,
  settings, and backup/restore all keep working.
- **Backup / Restore**: the existing Copy Backup and Restore controls continue
  to round-trip a couple's state, and a restore reconciles with the account
  rather than silently diverging from it.
- **"Reset everything"**: the wording now has two possible meanings. It clears
  the account's swipe state and the device's cache both, so a reset is a reset
  everywhere the user can see — and the confirmation dialog says so plainly.
- **"Start [name] over"**: unchanged in meaning, clearing just that swiper's
  picks, now on the account rather than the device.
- **Undo across a block boundary**: undo remains available for what the swiper
  has actioned in the current session and does not desynchronize the served
  order.
- **Corpus updated server-side**: names already swiped keep their place in the
  served order and continue to appear in Matches, per 001's rule that matches
  derive from picks and never from the current pool.
- **Account deletion / sign-out on a shared device**: signing out clears the
  cached state from that device so the next person to open the app does not see
  someone else's names.
- **A swiper reaches the end of the corpus**: the app says so plainly rather
  than showing an empty deck.

## Requirements *(mandatory)*

### Functional Requirements

**Accounts and access**

- **FR-001**: Users MUST be able to create an account, sign in, and sign out
  using the hosting platform's built-in authentication, with no bespoke
  credential handling.
- **FR-002**: Sessions MUST persist across app restarts so routine use does not
  require repeated sign-in.
- **FR-003**: One account MUST hold both swipers ("you" and "partner"), exactly
  as one browser does today. Linking two accounts is out of scope.
- **FR-004**: All state MUST be scoped to its owning account. No request MUST
  be able to read or modify another account's names, picks, or settings.
- **FR-005**: Signing out MUST clear cached account state from the device.

**State ownership and parity**

- **FR-006**: The service MUST store, per account: both swiper labels, the last
  name, the gender filter, the onboarded flag, and every pick keyed by name
  with its keep/no value.
- **FR-007**: The app MUST retain full feature parity with the current release
  — Welcome, swipe, Matches, Settings, backup/restore, the update toast, and
  every existing interaction behaves as it does today.
- **FR-008**: Matches and keeps MUST continue to derive from recorded picks
  rather than from the active pool, preserving 001's guarantee that a swiped
  name never vanishes from Matches.
- **FR-009**: The existing on-device save under `babyname-swipe-v3` MUST remain
  the offline cache. The key MUST NOT be renamed, and schema changes to its
  value MUST follow the existing backward-compatible migration pattern.
- **FR-010**: Backup and restore MUST continue to round-trip a couple's state
  and MUST reconcile a restore with the account rather than leaving the two
  divergent.

**Names and served order**

- **FR-011**: The service MUST own the global name list and serve names to the
  app in blocks. The frontend MUST NOT ship the corpus.
- **FR-012**: The service MUST record the order in which names are dealt to an
  account, shared by both swipers, so that both swipers see the same names in
  the same order — the record [003](../003-ai-name-filter/spec.md) builds on.
- **FR-013**: Served names MUST honor the account's girl/boy/both filter and
  preserve today's ordering character: familiar names first, with occasional
  deeper draws, and identical ordering for both swipers on the account.
- **FR-014**: The system MUST never serve a duplicate — no name appears twice
  in an account's served order, and no name is re-served to a swiper who
  already swiped it.
- **FR-015**: Girl and boy name sets MUST continue to share zero spellings, so
  that picks keyed by name alone cannot collide across genders.
- **FR-016**: When a swiper has genuinely reached the end of the available
  names, the app MUST say so plainly rather than presenting an empty deck.

**Offline and sync**

- **FR-017**: Once a block is loaded, swiping, undo, and Matches MUST work
  fully offline, with no perceptible delay and no error state.
- **FR-018**: Picks made offline MUST be held on the device and synced to the
  account automatically when connectivity returns or when the next block is
  requested, whichever comes first.
- **FR-019**: Sync MUST be idempotent and safe to retry: repeating or
  interrupting it MUST produce the same result as one clean sync, with no
  duplicated, dropped, or reordered picks.
- **FR-020**: The next block MUST be requested before the current one is
  exhausted, so an online swiper never waits at the end of a block.
- **FR-021**: If the block is exhausted while offline, the app MUST show a
  friendly explanation, preserve all picks and matches, and resume on its own
  when connectivity returns.
- **FR-022**: Concurrent use of one account on two devices MUST converge: the
  service owns the served order, and the most recent value for a given
  (swiper, name) pick wins.

**Migration**

- **FR-023**: On a user's first sign-in, existing on-device state MUST be
  imported into their account exactly once, without discarding any pick and
  without forcing the user back through onboarding. The import MUST be safe to
  retry, and the on-device copy MUST be preserved until the import is
  confirmed.

**Operations and development**

- **FR-024**: Recurring cost MUST stay within the ceiling agreed at planning
  time, with the cheapest viable hosting tier chosen and spend safeguards in
  place ([NEEDS CLARIFICATION] Q2).
- **FR-025**: The repository MUST contain no credentials. Deployment
  credentials are supplied out-of-band, and a written runbook MUST make the
  manual deploy repeatable by someone who has not done it before.
- **FR-026**: Database schema changes MUST be applied as ordered, versioned
  migrations with a recorded applied state.
- **FR-027**: A single command MUST run linting, strict type checking, and the
  full test suite against a disposable database, requiring no manual setup and
  no shared local database, and MUST report one overall pass/fail.
- **FR-028**: Every behavioral change MUST originate as a test that fails
  before the implementation that satisfies it exists.
- **FR-029**: The service MUST expose a health signal sufficient to tell
  "deployed and serving" from "deployed and broken" without reading logs.

**Open**

- **FR-030**: Whether the app can be used at all without an account MUST be
  settled before planning ([NEEDS CLARIFICATION] Q1).

### Key Entities

- **Account**: a signed-in user, owning exactly one couple's state. Created via
  the platform's built-in auth; no profile data of its own beyond what the app
  already collects.
- **Couple State**: the two swiper labels, last name, gender filter, and
  onboarded flag — today's persisted object, now owned by an account.
- **Pick**: one swiper's keep/no verdict on one name, keyed by name string
  rather than position, so changes to the name list never orphan it.
- **Name**: an entry in the global list, with a gender and a popularity rank.
  Owned by the service; no longer shipped to the device.
- **Served Order**: the record of names dealt to an account and each swiper's
  position within it. Shared by both swipers. This is the plumbing
  [003](../003-ai-name-filter/spec.md) rebuilds from beyond the furthest
  swiper's position.
- **Block**: a contiguous run of names handed to a device at once, sized to
  cover a realistic offline session. The unit of both delivery and sync.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who signs in on a brand-new browser sees 100% of their
  picks, matches, profile names, last name, and gender filter restored, with
  the first card on screen within 3 seconds on a normal connection.
- **SC-002**: A user with existing on-device history who signs in for the first
  time keeps 100% of their picks, with zero duplicates after repeated sign-ins,
  and is never returned to onboarding.
- **SC-003**: A swiper can complete a full block offline — every card, undo,
  and the Matches screen — with zero errors, and 100% of those picks reach the
  account within 10 seconds of connectivity returning.
- **SC-004**: An online swiper can go through 500+ names in a session without
  a repeated name, without an empty-deck state, and without a visible pause at
  any block boundary.
- **SC-005**: Both swipers on an account are served identical names in
  identical order, verified across two devices.
- **SC-006**: Interrupting a sync at any point and retrying produces state
  identical to an uninterrupted sync, across at least 20 randomized
  interruption points.
- **SC-007**: No account can read or modify another account's data — verified
  by test, not by inspection.
- **SC-008**: Recurring monthly cost stays within the agreed ceiling, with a
  measured figure recorded after the first full month.
- **SC-009**: `make check` runs green on a clean clone with no manual setup, in
  under 5 minutes, and every behavior in this feature traces to a test that
  failed before its implementation existed.
- **SC-010**: Following the deploy runbook from scratch produces a working
  service, and the repository contains zero credentials at every commit.
- **SC-011**: The frontend bundle shrinks by roughly 217 KB gzip once the
  corpus is no longer shipped, and cold load is no slower than today's.

## Assumptions

- **One account is one couple.** Both swipers share it, matching how one
  browser works today. This is what "accounts, but partners not linked yet"
  means, and it keeps matching semantics untouched.
- **The service is the sole source of names.** The bundled corpus is removed
  rather than kept as a fallback — two sources of truth for the deck would
  diverge, and removing it is where the bundle-size win comes from. The
  consequence is that a brand-new user with no cached block needs one
  successful connection before their first card.
- **Block size is a planning decision**, sized so a realistic offline session
  fits inside one block. Roughly 100 names is the working assumption, matching
  the batch size 003 already specifies.
- **Auth is email and password via the platform's built-in provider**, with
  persistent sessions — the least-work option consistent with "nothing fancy."
  Social sign-in and passwordless flows are not ruled out later; they are just
  not worth the setup now.
- **Existing local users are few and known**, so a one-time import path that
  covers the documented save shapes (current and legacy) is sufficient; no
  general-purpose data-recovery tooling is needed.
- **The frontend stays where it is** — Azure Static Web Apps, deployed by the
  existing hand-written workflows. Only the backend is hand-deployed, and only
  until the next spec.
- **The name corpus content is unchanged** from 001. This spec moves it; it
  does not curate, extend, or re-derive it.
- **`babyname-swipe-v3` keeps its name and its role** as the offline cache. It
  stops being the only copy of a couple's history, which is the point.

## Clarifications needed

Two decisions have no reasonable default and materially change the work.

### Q1: Is an account required to use the app at all?

**Context**: FR-030. Today anyone can open the app and start swiping with no
sign-up. Accounts are being added for durability, not for gating.

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Account required — sign-in is the first screen | Simplest to build and reason about; one state model, one sync path. Costs the app its zero-friction open-and-swipe start, and every new visitor hits a signup wall. |
| B | Guest mode, with an optional upgrade to an account later | Preserves today's instant start; a guest's local swipes import when they eventually sign up. Meaningfully more work: two state models, and the import path from User Story 4 becomes a permanent feature rather than a one-time migration. |
| C | Account required, but signup is one tap (passwordless / magic link) | Keeps a single state model while softening the wall. Friction is an email round-trip on first use rather than a password to invent. |
| Custom | Provide your own answer | Describe when a user should first be asked to identify themselves. |

### Q2: What is the monthly cost ceiling for the backend?

**Context**: FR-024, SC-008. Constitution II requires that a metered feature
carry an explicit, user-approved budget and safeguards against unbounded spend.
This is the first server-side component in the project's history.

| Option | Answer | Implications |
|--------|--------|--------------|
| A | $0 — free tiers only, hard stop | Constrains hosting to free allowances and accepts their limits, including cold starts and the possibility of a paused database on idle. Truest to the constitution as written. |
| B | A small fixed ceiling (e.g. $10–25/month) | Buys an always-warm service and a database that will not pause, removing the worst of the free-tier user-visible symptoms. Requires spend alerts and a documented tripwire. |
| C | Free tiers now, with a pre-agreed ceiling if usage forces an upgrade | Starts at zero and avoids deciding twice; the ceiling exists so an upgrade is not an emergency. Needs the trigger condition written down. |
| Custom | Provide your own answer | State the ceiling and what should happen when it is approached. |
