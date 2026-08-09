# Feature Specification: AI Name Filter

**Feature Branch**: `expanded-name-corpus`

**Created**: 2026-08-08

**Status**: Draft — clarifications resolved 2026-08-08; split 2026-08-08

**Depends on**: [001-expanded-name-corpus](../001-expanded-name-corpus/spec.md)
— the bundled real-name corpus this feature filters. That corpus ships
complete and uncurated (~106,000 names), on the explicit understanding that
narrowing it is *this* feature's job.

**Commercial context (2026-08-08)**: the owner expects criteria filtering to
become a **paid tier**. That does not change what this spec requires, but it
does change the Constitution II calculus at planning time — per-device rate
caps on a free allowance versus usage funded by subscription revenue are
different cost models, and the plan phase should settle which applies before
sizing caps.

**Input**: User description: "I want to enable an AI enabled name filter. As an exercise to load the initial names into the app, I told AI to generate a whole bunch of names that meet a specific criteria… no names that end in ey or similar sounds among others. I want to enable a feature to do so for everyone. Basically the user can describe the names they like in settings and then the app generates names that fit that criteria? And maybe it does 100 at a time or whatever makes sense so that the list is effectively infinite? Or, does it make sense to start from a big list of names from online somewhere and then filter off of that?"

**Clarifications (2026-08-08)**: (1) Criteria-driven decks replace the deck
beyond the furthest swiper's position only; everything either partner actioned
is immutable. (2) Cost model: an app-provided service with per-device rate
caps. (3) Names are always drawn from the bundled corpus — criteria filter it
down in two stages, both AI-assisted but in different roles: stage one, AI
translates the user's free text into deterministic rules within a defined rule
framework that the filtering engine executes exactly; stage two, AI judges
candidate names against whatever in the description is genuinely subjective.
See [research.md](research.md).

**Why deck bookkeeping starts here**: until this feature, the deck is a static
list in a fixed order, so both swipers walk the same path with no state beyond
their own picks. This is the first feature that can *change* the deck
mid-flight, which is what makes an explicit served-order record necessary
(User Story 3).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Describe criteria, get a personalized deck (Priority: P1)

A parent opens Settings and finds a "Name preferences" field where they
describe, in their own words, what kinds of names they want to see — for
example: "classic but not stuffy, two syllables or fewer, nothing ending in an
'ee' sound, nothing starting with D." After saving, the upcoming (not yet
swiped) deck is rebuilt from the bundled corpus to fit that description,
tagged girl/boy appropriately and respecting the existing girl/boy/both
filter.

**Why this priority**: This is the feature. The app's original pool encoded
one couple's constraints at build time; this story hands that same power to
every user at runtime.

**Independent Test**: With the corpus feature (001) in place, enter a
distinctive criteria description (e.g. "nature-inspired names, one or two
syllables"), return to the swipe screen, and verify the next cards are corpus
names matching the description with correct gender tags.

**Acceptance Scenarios**:

1. **Given** a user with no criteria set, **When** they enter a criteria
   description in Settings and return to swiping, **Then** upcoming cards are
   corpus names that fit the described criteria.
2. **Given** a criteria description that includes an objective exclusion (e.g.
   "nothing ending in an 'ee' sound"), **When** personalized names are served,
   **Then** zero served names violate the exclusion.
3. **Given** a criteria description that includes a subjective quality (e.g.
   "feels classic"), **When** personalized names are served, **Then** the
   overwhelming majority of served names visibly fit that quality.
4. **Given** the gender filter is set to "girl", **When** personalized names
   are served, **Then** only girl-tagged names appear and the card's color
   band behaves exactly as it does today.

---

### User Story 2 - The deck never runs dry (Priority: P2)

As either parent swipes, the app keeps the upcoming deck topped up — extending
it in batches of roughly 100 names ahead of the furthest swiper — so the deck
feels effectively infinite while matching names remain in the corpus. New
names never duplicate anything either swiper has already seen or anything
already queued.

**Why this priority**: "Effectively infinite" is the stated goal; a single
batch already delivers value, replenishment keeps the app useful past the
first session.

**Independent Test**: Set criteria, swipe through more names than one batch
contains, and verify matching names keep appearing with no "deck empty" state
and no repeats.

**Acceptance Scenarios**:

1. **Given** the upcoming deck is running low, **When** the swiper continues,
   **Then** additional matching names are appended without interrupting the
   swipe flow.
2. **Given** replenishment would surface a name either swiper has already
   swiped or that is already queued, **Then** that name is skipped.
3. **Given** the device is offline or the AI service is unavailable, **When**
   the swiper exhausts the locally available deck, **Then** the app shows a
   friendly "more names when you're back online" style message instead of an
   error, and all existing picks and matches remain intact.
4. **Given** a criteria so restrictive that the corpus is genuinely exhausted,
   **Then** the app says so plainly ("you've seen every name matching this
   description") and suggests loosening the criteria.

---

### User Story 3 - Change your mind without breaking your partner's path (Priority: P2)

A couple realizes halfway through that their criteria was too narrow. One of
them edits the criteria text in Settings. Everything either partner has
already swiped stays exactly as it was — and the partner who is behind still
replays the same names, in the same order, that the leading partner already
went through. Only the deck beyond the furthest swiper's position follows the
new criteria.

**Why this priority**: This is what keeps matching trustworthy once the deck
can change. Without it, a criteria edit would strand the trailing partner on a
different set of names than the leading partner swiped, quietly destroying
potential matches.

**Independent Test**: With partner A 50+ names ahead of partner B, change the
criteria; verify partner B's next cards are the names A already swiped, in A's
order, and that cards beyond A's position follow the new criteria.

**Acceptance Scenarios**:

1. **Given** existing picks and matches, **When** the criteria text is edited,
   **Then** all existing picks and matches are preserved exactly.
2. **Given** partner A has swiped 200 names and partner B has swiped 100,
   **When** partner B continues swiping after a criteria change, **Then**
   partner B is served names 101–200 in exactly the order partner A saw them,
   before any names produced by the new criteria.
3. **Given** the criteria was edited, **When** the deck beyond the furthest
   swiper's position is rebuilt, **Then** queued-but-unswiped names that no
   longer match are discarded and replaced by names matching the new criteria.
4. **Given** the criteria is cleared entirely, **When** the user returns to
   swiping, **Then** the deck beyond the furthest swiper's position reverts to
   the unfiltered corpus, and all swiped history still stands.

---

### Edge Cases

- **Impossible or contradictory criteria** (e.g. "names with no vowels"): the
  system serves its best effort and, when it cannot produce a reasonable
  batch, tells the user their description may be too restrictive rather than
  failing silently or showing junk.
- **Offensive or off-topic criteria text**: the system declines gracefully and
  asks the user to rephrase; it never lets such text degrade the deck into
  offensive content.
- **First criteria set on an in-progress deck**: names already swiped by
  either partner are frozen as-is; the new criteria applies from the furthest
  swiper's position onward, so a trailing partner still replays what the
  leading partner saw.
- **Rate cap reached** (per-device cap on the AI service): swiping continues
  through everything already queued; if the queue empties while capped, the
  user sees a friendly "more names soon" message. Criteria whose description
  translated entirely into deterministic rules keep working without the
  service at all.
- **Reset everything**: the existing device reset also clears criteria and
  deck-order state.
- **Two devices**: the app has no sync; two devices with the same criteria may
  build different decks. Cross-device consistency remains out of scope,
  matching the app's existing posture.
- **Storage growth**: the served-order record grows only with names actually
  swiped, the pending queue stays bounded (roughly one batch beyond the
  furthest swiper), and cached AI verdicts must also stay bounded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to enter, edit, and clear a free-text
  description of their name preferences in Settings, following the screen's
  existing auto-save behavior.
- **FR-002**: When a criteria description is set, the system MUST serve only
  names from the bundled corpus that match it, honoring the active
  girl/boy/both filter and today's card presentation rules.
- **FR-003**: Criteria interpretation is AI-driven in two distinct roles.
  First, AI MUST translate the user's free text into deterministic rules
  expressed in a defined rule framework (a fixed vocabulary of checks such as
  starting letters, ending letters/sounds, length) that the filtering engine
  then executes exactly, with zero violations. Second, only what remains
  genuinely subjective after that translation (e.g. "feels classic", "modern
  but not trendy") is handled by AI judgment over the candidate names, holding
  for the overwhelming majority of served names. Anything expressible as a
  deterministic rule MUST be handled by the first role, not the second.
- **FR-004**: The app MUST record the order in which names are served, so that
  every name actioned by at least one swiper is frozen: its place in the order
  never changes, and it is replayed to the other swiper in that same order
  before any newer names.
- **FR-005**: Only the portion of the served order beyond the furthest
  swiper's position may be rebuilt. A criteria change (edit, or clear) MUST
  rebuild exactly that portion, MUST preserve all picks and matches, and MUST
  take effect from that point onward.
- **FR-006**: The upcoming deck MUST be extended in batches of approximately
  100 names, replenished before the furthest swiper reaches the end, so an
  online user never hits an end-of-deck state while matching names remain in
  the corpus.
- **FR-007**: The system MUST never serve a duplicate: no name appears twice
  in the served order, and no name is re-served to a swiper who already swiped
  it.
- **FR-008**: The criteria text, served-order record, and swiper positions
  MUST persist across restarts within the existing on-device save under the
  existing storage key via backward-compatible migration (per Constitution
  IV), and MUST round-trip through the existing backup/restore flow.
- **FR-009**: AI-backed steps MUST run through an app-provided service with
  per-device rate caps that bound worst-case monthly cost to a figure agreed
  at planning time (per Constitution II). Hitting a cap MUST degrade softly:
  already-queued names keep serving, and criteria that translated entirely
  into deterministic rules continue to work without the service.
- **FR-010**: When the AI service is unavailable (offline, failure, capped),
  the app MUST degrade gracefully: swiping the existing queue, matches,
  backup/restore, and settings all keep working, and the user sees a friendly
  explanation rather than an error state.
- **FR-011**: All new UI MUST follow the app's muted visual language and
  minimal-motion rules (Constitution I), and new inputs MUST follow the
  existing mobile input conventions (e.g. no-zoom text sizing).

### Key Entities

- **Name Criteria**: the user's free-text description of desired names; one
  per device, shared by both swipers; editable and clearable at any time.
- **Interpreted Criteria**: the translation of that text into (a) rules in the
  deterministic rule framework and (b) a residual subjective brief; refreshed
  whenever the criteria text changes.
- **Served Order**: the persisted record of names dealt on this device, shared
  by both swipers, with each swiper's position in it; the portion up to the
  furthest swiper's position is immutable history, the remainder is a
  rebuildable queue (bounded to roughly one batch).
- **Name Corpus / Picks**: as established in
  [001-expanded-name-corpus](../001-expanded-name-corpus/spec.md); unchanged
  here.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who saves a criteria description sees their first
  matching name cards within 15 seconds, without leaving the app.
- **SC-002**: Objective criteria are exact: a stated exclusion (e.g. "no 'ee'
  endings") shows zero violations across any sample of served names.
  Subjective qualities hold for at least 19 of every 20 served names on
  spot-check.
- **SC-003**: An online swiper with criteria set can swipe 500+ names in a
  session without an empty deck or a repeated name (unless the criteria has
  genuinely exhausted the corpus, which the app states plainly).
- **SC-004**: Criteria edits never touch history: 100% of picks and matches
  survive any criteria change, and in a two-swiper test the trailing swiper
  receives 100% of the leading swiper's actioned names, in identical order,
  before any newly generated names.
- **SC-005**: Monthly operating cost attributable to this feature stays within
  the cap chosen at planning time, demonstrated by test: a device exceeding
  its rate cap is throttled and the app degrades softly per FR-009/FR-010.
- **SC-006**: Criteria that translate entirely into deterministic rules incur
  zero AI-service usage after the initial translation call.

## Assumptions

- **One criteria per device, shared by both swipers.** Matching requires both
  partners to swipe the same names, so criteria (like the deck) is a
  couple-level setting, not per-swiper.
- **Criteria entry lives in Settings only for this release.** The Welcome
  (onboarding) flow is unchanged; a first-run criteria prompt could be a
  future enhancement.
- **The corpus from 001 is in place** before this feature ships; this spec
  adds no corpus content. Because that corpus is complete and uncurated, the
  unfiltered deck contains many rare spellings — making "narrow this down to
  names we'd actually consider" the feature's core value, not a refinement.
- **Existing saves have no served-order record**, so migration reconstructs a
  starting point from the app's prior deterministic ordering and each swiper's
  picks; the replay guarantee applies from that point forward.
- **Internet connectivity is required only for the AI steps** (criteria
  translation and subjective judgment); deterministic filtering runs entirely
  on-device.
- **The rule framework's vocabulary is a planning-phase design decision** — it
  draws the line between criteria that are free/exact and those needing the
  metered subjective stage.
