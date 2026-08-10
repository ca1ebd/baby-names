# Feature Specification: Backend, Accounts & Sync

**Feature Branch**: `backend-accounts-sync`

**Created**: 2026-08-10

**Status**: Draft — no open clarifications. Pre-release confirmed, Principle
III deviation granted, account model and cost posture clarified 2026-08-10.

**Depends on**: [001-expanded-name-corpus](../001-expanded-name-corpus/spec.md)
— the name corpus this feature moves off-device and serves from the backend.

**Blocks**: [003-ai-name-filter](../003-ai-name-filter/spec.md) — criteria
filtering was originally 002 and was renumbered on 2026-08-10 when the owner
judged that building it on purely local state was the cart before the horse.
The served-order record that 003 assumed it would have to invent is now this
spec's plumbing (User Story 2, FR-013/FR-014).

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

This feature is a **re-platforming, not a new user-facing capability**. Its
success condition is that a couple using the app notices almost nothing except
that they now sign in, and that their swipes survive losing their phone.
Everything the app does today — the deck, the segmented swiper control,
matches, settings, backup/restore, the update toast — must still work
identically afterward.

**The app is pre-release.** There is no production data and no installed base,
so this spec carries no data-migration obligation — the riskiest part of a
change like this simply does not apply. It also means the local-only mode goes
away rather than being maintained alongside accounts.

Four things are explicitly **out of scope** and belong elsewhere:

- **Partner linking.** One account holds both swipers, exactly as one browser
  does today. Two people with two accounts sharing a deck is a later feature.
- **CI/CD.** This release deploys by hand. Automating it is the next spec, and
  deliberately so — see the accepted deviation below.
- **Criteria filtering.** That is [003](../003-ai-name-filter/spec.md), which
  builds on the plumbing this spec lays down.
- **Migrating existing on-device saves.** Nothing to migrate; see above.

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
  set at $0 (free tiers only) on 2026-08-10; see FR-024 and SC-007.
- **Principle III (Pipeline-Only Deployments)** — as written, this principle
  prohibits manual deploys to production. Backend deploys in this release are
  manual. **Resolution: accepted as a time-boxed deviation, granted by the
  owner on 2026-08-10.** See "Accepted deviation" below. The principle itself
  is not amended; the frontend remains pipeline-only and unaffected.
- **Principle IV (Storage Key Stability)** — `babyname-swipe-v3` remains the
  on-device key and MUST NOT be renamed, even though its role changes: it stops
  being the system of record and becomes the offline cache. The value's shape
  changes substantially (it must now hold a block of undealt names and a queue
  of unsynced picks), and that evolution happens inside the value, per the
  principle. Nothing in this feature may force a user back through onboarding
  or discard a pick.
- **Principle I (Muted Visual Design)** — the new sign-in surface is the first
  screen a user sees, and it follows the app's existing muted language, minimal
  motion, and mobile input conventions (`fontSize: 16`, safe-area insets,
  `minWidth: 0` on flex children).

### Accepted deviation: manual backend deploys (Principle III)

**Granted**: 2026-08-10, by the owner.

**Scope**: backend service and database only. Frontend production deploys stay
pipeline-only through the existing hand-written workflows, unchanged.

**Rationale**: automating a deploy path before it has been walked once by hand
encodes guesses. The first manual deploys are how the project learns what the
pipeline actually needs to do — what has to be configured, what breaks, what
order things must happen in. Building CI/CD first would mean writing a pipeline
against an unknown target and then rewriting it.

**Expiry**: the next spec, which covers backend CI/CD. This deviation ends when
that work ships. It does not renew by default; extending it requires the same
explicit grant again.

**Compensating controls** while it is in force: `make check` is the gate
(FR-027, FR-028), deploys follow a written runbook rather than improvisation
(FR-025), schema changes go through ordered versioned migrations (FR-026), and
the service exposes a health signal so a broken deploy is visible without
reading logs (FR-029).

## Clarifications

### Session 2026-08-10

- Q: Should someone be able to open the app and start swiping without making an
  account, or is signing in the first thing they do? → A: Option C — an
  account is required, created and entered by passwordless email magic link.
  No guest or anonymous mode. (Now FR-001/FR-002.)
- Q: How much per month is the backend allowed to cost, and what happens if
  usage pushes past it? → A: Option A — $0, free tiers only, hard stop. Cold
  starts are mitigated by warming the service and database as soon as the app
  loads, seconds before any request is actually needed, rather than by paying
  for always-warm hosting. (Now FR-024, FR-030, SC-007.)
- Q: Should every account get its own shuffled name order, or should all
  accounts be dealt the same global sequence? → A: Option A — each account gets
  its own deterministic shuffle, seeded from the account, shared by both
  swipers on it. The fixed global seed `20260730` retires. (Now FR-014.)
- Q: Should the API limit how many requests one account can make, and what
  happens when it goes over? → A: Option B — a per-account request cap set far
  above realistic human use; over-limit requests are refused and surface as the
  app's friendly waiting state. No per-IP limiting this release. (Now FR-032.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Your swipes belong to you, not to a browser (Priority: P1)

A parent creates an account and signs in. Everything the app knows about them —
both swipers' names, the last name, the girl/boy/both filter, and every pick
either of them has made — is stored in their account. Signing in from a
different browser, a reinstalled app, or a replacement phone brings all of it
back exactly as it was.

**Why this priority**: This is the whole point of the re-platforming. In the
current design a cleared browser cache would be unrecoverable loss for a couple
who had swiped thousands of names — a liability worth removing before anyone
has anything to lose.

**Independent Test**: Sign in, swipe a distinctive set of names, sign in as the
same account in a fresh browser profile, and verify the picks, matches,
profile names, and gender filter all match.

**Acceptance Scenarios**:

1. **Given** a new visitor, **When** they create an account and complete the
   existing Welcome flow, **Then** their profile and settings persist to their
   account and the swipe screen behaves exactly as it does today.
2. **Given** a visitor who is not signed in, **When** they open the app,
   **Then** they are asked to sign in, and no deck, picks, or settings are
   reachable until they do.
3. **Given** a signed-in user with picks recorded, **When** they sign in on a
   different device or browser, **Then** every pick, match, profile name, last
   name, and the gender filter are restored identically.
4. **Given** a signed-in user, **When** they sign out and back in, **Then** no
   state is lost and they are not sent back through onboarding.
5. **Given** two different accounts, **When** either signs in, **Then** neither
   can see or affect any part of the other's names, picks, or settings.
6. **Given** a signed-in session, **When** the app is reopened days later,
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
6. **Given** two different accounts with the same gender filter, **Then** their
   decks are in visibly different orders, and each account's own order is
   reproducible run after run.

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

### User Story 4 - A dev loop the agent can run unattended (Priority: P2)

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

### User Story 5 - Hand-deploy the service (Priority: P3)

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
- **Magic link opened on a different device than requested**: the link signs in
  the device that opens it, and the requesting device is not left stranded — it
  either completes sign-in or clearly invites the user to try again.
- **Magic link never arrives, or is used twice**: the app offers a resend
  without losing whatever was already typed, and an already-consumed or expired
  link produces a plain "this link has expired, request a new one" rather than
  an error state.
- **Account hits the request cap**: swiping continues through everything
  already in the loaded block, since that needs no network. If the block empties
  while capped, the user sees the same "more names shortly" waiting state as
  when offline, and normal service resumes when the window rolls over. No pick
  is lost and nothing is presented as an error.
- **Free-tier database suspended after prolonged inactivity**: a warm-up ping
  keeps the project active only while somebody opens the app; a stretch with no
  users at all can still put the database to sleep in a way that a ping does
  not wake on its own. The app treats this as the waiting state (FR-031), and
  the plan phase must establish what the hosting tier actually does after
  extended idleness and whether recovery needs a manual step.
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

- **FR-001**: An account is REQUIRED to use the app. There is no guest or
  anonymous mode, and no swiping happens before sign-in.
- **FR-002**: Users MUST be able to create an account, sign in, and sign out by
  passwordless email magic link, using the hosting platform's built-in
  authentication. The app MUST NOT handle passwords, which means no
  password-entry, forgot-password, or change-password surface exists. For this
  release, delivery is limited to pre-authorized addresses — see Assumptions.
- **FR-003**: Sessions MUST persist across app restarts so routine use does not
  require repeated sign-in.
- **FR-004**: One account MUST hold both swipers ("you" and "partner"), exactly
  as one browser does today. Linking two accounts is out of scope.
- **FR-005**: All state MUST be scoped to its owning account. No request MUST
  be able to read or modify another account's names, picks, or settings.
- **FR-006**: Signing out MUST clear cached account state from the device.

**State ownership and parity**

- **FR-007**: The service MUST store, per account: both swiper labels, the last
  name, the gender filter, the onboarded flag, and every pick keyed by name
  with its keep/no value.
- **FR-008**: The app MUST retain full feature parity with the current release
  — Welcome, swipe, Matches, Settings, backup/restore, the update toast, and
  every existing interaction behaves as it does today.
- **FR-009**: Matches and keeps MUST continue to derive from recorded picks
  rather than from the active pool, preserving 001's guarantee that a swiped
  name never vanishes from Matches.
- **FR-010**: The on-device save under `babyname-swipe-v3` MUST become the
  offline cache. The key MUST NOT be renamed; its value's shape may change
  freely, since the app is pre-release and no save in the wild depends on it.
- **FR-011**: Backup and restore MUST continue to round-trip a couple's state
  and MUST reconcile a restore with the account rather than leaving the two
  divergent.

**Names and served order**

- **FR-012**: The service MUST own the global name list and serve names to the
  app in blocks. The frontend MUST NOT ship the corpus.
- **FR-013**: The service MUST record the order in which names are dealt to an
  account, shared by both swipers, so that both swipers see the same names in
  the same order — the record [003](../003-ai-name-filter/spec.md) builds on.
- **FR-014**: Each account MUST get its own name order, derived
  deterministically from a seed belonging to that account, so the same account
  always reproduces the same sequence while different accounts get different
  ones. The order MUST honor the account's girl/boy/both filter and preserve
  today's ordering character — familiar names first, with occasional deeper
  draws — and MUST be identical for both swipers on the account. The fixed
  global seed the frontend uses today is retired: determinism now comes from
  the account's own seed rather than from a constant shared by every user.
- **FR-015**: The system MUST never serve a duplicate — no name appears twice
  in an account's served order, and no name is re-served to a swiper who
  already swiped it.
- **FR-016**: Girl and boy name sets MUST continue to share zero spellings, so
  that picks keyed by name alone cannot collide across genders.
- **FR-017**: When a swiper has genuinely reached the end of the available
  names, the app MUST say so plainly rather than presenting an empty deck.

**Offline and sync**

- **FR-018**: Once a block is loaded, swiping, undo, and Matches MUST work
  fully offline, with no perceptible delay and no error state.
- **FR-019**: Picks made offline MUST be held on the device and synced to the
  account automatically when connectivity returns or when the next block is
  requested, whichever comes first.
- **FR-020**: Sync MUST be idempotent and safe to retry: repeating or
  interrupting it MUST produce the same result as one clean sync, with no
  duplicated, dropped, or reordered picks.
- **FR-021**: The next block MUST be requested before the current one is
  exhausted, so an online swiper never waits at the end of a block.
- **FR-022**: If the block is exhausted while offline, the app MUST show a
  friendly explanation, preserve all picks and matches, and resume on its own
  when connectivity returns.
- **FR-023**: Concurrent use of one account on two devices MUST converge: the
  service owns the served order, and the most recent value for a given
  (swiper, name) pick wins.

**Operations and development**

- **FR-024**: Recurring cost MUST be $0. Only free hosting and database tiers
  may be used, and no paid tier may be adopted without a new explicit grant
  from the owner. Any configuration capable of incurring a charge MUST be
  treated as a defect, and spend alerts MUST be in place to catch one.
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

**Performance under free-tier hosting**

- **FR-030**: The app MUST issue a warm-up request to the service as soon as it
  loads — before sign-in, and before any request whose result the user is
  waiting on — so that a scaled-to-zero service and a sleeping database wake
  during sign-in rather than while the user stares at an empty deck. The
  warm-up MUST be cheap, MUST touch the database rather than the service alone,
  and MUST NOT block the UI or produce a visible error when it fails.
- **FR-031**: When the service or database is waking, unreachable, or
  suspended, the app MUST show the same friendly waiting state it uses when
  offline and retry on its own, never a raw error.

**Abuse protection**

- **FR-032**: The service MUST cap how many requests a single account can make
  in a given window. The cap MUST sit far enough above realistic human use that
  a couple swiping continuously never reaches it, and MUST be low enough to
  stop a runaway client from exhausting the free-tier allowance. Refused
  requests MUST surface to the user as the friendly waiting state (FR-031),
  never as an error, and MUST NOT cost the user any pick already recorded.
  Per-IP limiting on sign-in and unauthenticated endpoints is out of scope for
  this release.

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
  position within it, generated from the account's own seed. Shared by both
  swipers. This is the plumbing
  [003](../003-ai-name-filter/spec.md) rebuilds from beyond the furthest
  swiper's position.
- **Block**: a contiguous run of names handed to a device at once, sized to
  cover a realistic offline session. The unit of both delivery and sync.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who signs in on a brand-new browser sees 100% of their
  picks, matches, profile names, last name, and gender filter restored, with
  the first card on screen within 3 seconds of completing sign-in on a normal
  connection — including the case where the service and database were cold when
  the app was opened, since the warm-up runs during sign-in.
- **SC-002**: A swiper can complete a full block offline — every card, undo,
  and the Matches screen — with zero errors, and 100% of those picks reach the
  account within 10 seconds of connectivity returning.
- **SC-003**: An online swiper can go through 500+ names in a session without
  a repeated name, without an empty-deck state, and without a visible pause at
  any block boundary.
- **SC-004**: Both swipers on an account are served identical names in
  identical order, verified across two devices; two different accounts are
  served measurably different orders, and each account's order is reproducible
  across repeated runs.
- **SC-005**: Interrupting a sync at any point and retrying produces state
  identical to an uninterrupted sync, across at least 20 randomized
  interruption points.
- **SC-006**: No account can read or modify another account's data — verified
  by test, not by inspection.
- **SC-007**: The recurring monthly bill is $0, confirmed against the actual
  invoice after the first full month. Any nonzero charge is a defect.
- **SC-008**: `make check` runs green on a clean clone with no manual setup, in
  under 5 minutes, and every behavior in this feature traces to a test that
  failed before its implementation existed.
- **SC-009**: Following the deploy runbook from scratch produces a working
  service, and the repository contains zero credentials at every commit.
- **SC-010**: The frontend bundle shrinks by roughly 217 KB gzip once the
  corpus is no longer shipped, and cold load is no slower than today's.
- **SC-011**: A brand-new user gets from first launch to their first card in
  under 90 seconds including the email round-trip, and returning users reach
  the deck without any sign-in step at all.
- **SC-012**: A simulated runaway client is refused once past the cap, while a
  simulated session of continuous human swiping — an hour of uninterrupted
  swiping at a realistic rate — never trips it.

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
- **The app is pre-release: there is no production data to preserve.** Owner
  confirmed 2026-08-10. No migration of existing on-device saves is required,
  no legacy save shapes need supporting, and the offline cache's value shape
  can be redesigned freely. This removes what would otherwise have been the
  riskiest part of the feature. The `babyname-swipe-v3` key itself still MUST
  NOT be renamed (Constitution IV), and the local-only mode disappears in
  favor of the account.
- **Free-tier limits are accepted deliberately**, not overlooked. Scale-to-zero
  cold starts and idle suspension are the price of a $0 bill, and the warm-up
  path (FR-030) is the agreed mitigation rather than paid always-warm hosting.
  If the mitigation proves insufficient in practice, the answer is a new
  conversation about budget, not a quiet upgrade.
- **Sign-in works only for pre-authorized addresses this release.** Magic links
  are sent by the platform's built-in auth email service, which delivers only to
  addresses on the project team and caps at 2 messages per hour. Both users'
  addresses are added to the project directly; nobody else can create an
  account until a real email provider is configured. This is a deliberate
  deferral for a pre-release app with two known users — standing up a fourth
  external service to serve two allow-listed addresses is work with no payoff
  yet — and it is the one limit that must be lifted before anyone else can use
  the app. Tracked in [docs/remaining-items.md](../../docs/remaining-items.md).
  A practical consequence: automated tests MUST NOT exercise real email
  delivery, or the hourly cap will make the suite unrunnable.
- **The frontend stays where it is** — Azure Static Web Apps, deployed by the
  existing hand-written workflows. Only the backend is hand-deployed, and only
  until the next spec.
- **Deck ordering stays deterministic, just not global.** The property worth
  keeping from the seed-`20260730` design is reproducibility, not universality
  — the global seed only ever existed to make two devices agree without a
  server, which the account now does properly. The tuned first-20 distribution
  from 001 (median near rank 180, roughly one card in six from deeper) is a
  property of the weighting, not of the seed, and survives the change.
- **The exact rate-cap numbers are a planning decision.** The requirement fixes
  the shape — per-account, generous, soft-failing — while the window and
  threshold get set at plan time against measured block sizes and the free
  tier's actual allowance.
- **The name corpus content is unchanged** from 001. This spec moves it; it
  does not curate, extend, or re-derive it.
