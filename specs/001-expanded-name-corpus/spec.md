# Feature Specification: Expanded Name Corpus

**Feature Branch**: `expanded-name-corpus`

**Created**: 2026-08-08

**Status**: Draft

**Input**: Split from the original "AI Custom Name Deck" description: before
any AI filtering, swap the small hand-built name pool for a generic, much
larger list of real names. The AI criteria feature
([002-ai-name-filter](../002-ai-name-filter/spec.md)) then filters this list.

**Scope note**: This feature changes *what fills the deck*, nothing else. The
app's existing deck behavior — both swipers walking the same fixed order, each
skipping names they've already swiped — is a property of serving a static,
deterministically ordered list, and continues to hold with a larger list at no
extra cost. Machinery for a *changeable* deck belongs to 002, which is the
first feature that can change one.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A much bigger, generic default deck (Priority: P1)

A couple installs (or updates) the app and swipes as always — but instead of a
few hundred hand-picked names, the deck draws from a large bundled list of
real names (thousands per gender, derived from published real-world naming
data). Same cards, same colors, same matching; far more names before the deck
runs out, and no built-in stylistic restrictions.

**Why this priority**: This is the deliverable. It also becomes the universe
that the follow-on AI criteria feature filters, so it ships first.

**Independent Test**: On a fresh install, swipe past the size of the old pool
and verify names keep coming — all real names, no duplicates, correctly
gender-tagged.

**Acceptance Scenarios**:

1. **Given** a fresh install, **When** the user swipes, **Then** the deck is
   drawn from the bundled list and offers many times more names than the
   previous hand-built pool.
2. **Given** any deck state, **When** cards are served, **Then** every name is
   a real, established name from the bundled list — never an invented one.
3. **Given** the gender filter is "girl", "boy", or "both", **When** cards are
   served, **Then** only appropriately tagged names appear and the card color
   band behaves exactly as today.
4. **Given** "both" mode, **When** cards are served, **Then** no spelling ever
   appears in both the girl and boy pools.
5. **Given** either swiper, **When** they swipe, **Then** they encounter names
   in the same order as the other swiper (each skipping only names they
   personally already swiped), exactly as today.

---

### User Story 2 - Existing users upgrade without losing anything (Priority: P1)

A couple already mid-deck updates the app. Every pick, match, and profile
field survives — including keeps and matches for names that happen not to be
in the new list. Their Matches screen looks the same after the update as
before it.

**Why this priority**: Matches are the whole point of the app and the only
copy lives on the device. Silently dropping a matched name during a pool swap
would be unrecoverable data loss in the user's eyes, so this ranks alongside
the corpus swap itself.

**Independent Test**: On a save containing keeps and matches — including at
least one name deliberately absent from the new list — upgrade and verify the
Matches screen and each swiper's keeps are unchanged.

**Acceptance Scenarios**:

1. **Given** an existing save, **When** the app updates to the new corpus,
   **Then** 100% of picks, matches, and profile fields are preserved.
2. **Given** a name both partners kept that is not present in the new corpus,
   **When** the user opens the Matches screen after the upgrade, **Then** that
   match is still listed.
3. **Given** a name one partner kept that is not present in the new corpus,
   **When** that partner views their keeps, **Then** that name is still
   listed.
4. **Given** the upgrade, **When** either partner keeps swiping, **Then** they
   are never re-served a name they already swiped, and new names come from the
   new corpus.

---

### Edge Cases

- **Names dropped from the pool**: the old hand-built pool contained names
  that may not survive corpus curation. Their picks must remain honored and
  visible (User Story 2) even though they will never be dealt again.
- **Deck order changes at upgrade**: a larger list means a different overall
  order. Both swipers still walk the same new order as each other, so names
  one partner already swiped surface for the other partner wherever they fall
  in that order rather than immediately. This is a one-time, acceptable
  effect; matching is unaffected because picks are keyed by name.
- **Old stylistic restrictions retire**: the no-D-starts / no-"ey"-endings
  rules were build-time properties of the hand-built pool and are deliberately
  dropped — the app is generic now. Users who want such rules get them at
  runtime when 002 ships.
- **Obscure names in the unfiltered deck**: because the deck is shuffled and
  the corpus is complete, a rare spelling is dealt as readily as a common one.
  This friction is **accepted for this release** — narrowing the deck is the
  job of the criteria feature (002), not of a curated corpus. No quality cut
  is applied.
- **Corpus exhausted**: unreachable in practice at this corpus size, but the
  existing end-of-deck message stays as-is.
- **Storage growth**: the corpus ships with the app, not in the save; device
  storage does not grow beyond the existing per-name picks.
- **Backup/restore**: the existing copy/restore flow continues to round-trip
  all state unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST ship with a large built-in list of real names
  (thousands per gender, derived from published real-world naming data), each
  tagged girl or boy with no spelling in both pools, with popularity
  information retained for use by later features.
- **FR-002**: The corpus MUST be generic — it carries no stylistic
  restrictions of its own (the former no-D-starts / no-"ey"-endings rules are
  retired).
- **FR-003**: The default deck MUST be drawn from this list, honoring the
  girl/boy/both filter and today's card presentation exactly; the hand-built
  pool is retired.
- **FR-004**: The app MUST preserve today's deck behavior: a fixed order that
  is the same for both swipers, with each swiper served only names they have
  not personally swiped, and no name served twice.
- **FR-005**: The upgrade MUST preserve 100% of existing picks, matches, and
  profile fields, under the existing storage key with no key change (per
  Constitution IV).
- **FR-006**: Keeps and matches MUST remain visible after the upgrade even for
  names absent from the new corpus — the Matches screen and each swiper's
  keeps MUST reflect what the user actually swiped, not merely what the
  current corpus contains.
- **FR-007**: The feature MUST introduce no visual or interaction changes to
  the app beyond the larger name supply (Constitution I).

### Key Entities

- **Name Corpus**: the large built-in list of real names bundled with the app;
  each entry carries a spelling, one girl/boy tag, and popularity signal; the
  fixed universe decks draw from.
- **Picks (existing)**: each swiper's keep/pass record, keyed by name
  spelling; unchanged by this feature, and now the authoritative source for
  displaying keeps and matches.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The default deck offers the complete published corpus — every
  qualifying real name from the source data (~106,000, roughly 130x the
  previous hand-built pool) — and 100% of served names are real names from
  that list.
- **SC-002**: 100% of existing users' picks, matches, and profile fields
  survive the upgrade, including keeps and matches for names absent from the
  new corpus — verified by upgrading a save seeded with such a name.
- **SC-003**: In a two-swiper test, both swipers encounter names in the same
  relative order, and neither is ever served a name they already swiped.
- **SC-004**: A swiper can get through 500+ consecutive swipes with no empty
  deck, no repeats, and no perceptible slowdown versus today. Specifically:
  swipe-to-swipe response is unchanged, app start adds no more than ~200 ms on
  a mid-range phone, and switching swiper or gender filter stays under ~150 ms.
- **SC-005**: Match integrity holds: every name kept by both swipers appears
  on the Matches screen.

## Assumptions

- **Corpus sourcing**: derived from published, public real-world naming data
  (see [research.md](research.md)); each spelling assigned to exactly one
  gender pool by predominant usage, preserving the no-overlap invariant.
- **No popularity cut**: every valid spelling in the source is included. Deck
  quality is deliberately traded for completeness, on the expectation that
  criteria filtering (002) is where users narrow the field.
- **Corpus curation happens at build time** (a static artifact shipped with
  the app); no network access is needed for any behavior in this feature.
- **Deck ordering stays deterministic and shared**, as today — this is what
  makes both swipers walk the same path without any new bookkeeping. Only a
  feature that changes the deck at runtime (002) needs more than this.
- **A one-time reshuffle at upgrade is acceptable**; matching is unaffected
  because picks are keyed by name spelling.
- **English-language/Latin-script names** for the first release.
- **No new UI**: this feature changes what fills the deck, not how the app
  looks or is operated.
