# Implementation Plan: Expanded Name Corpus

**Branch**: `expanded-name-corpus` | **Date**: 2026-08-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-expanded-name-corpus/spec.md`

## Summary

Replace the 800-name hand-built `RAW` literal in `src/BabyNameSwipe.tsx` with a
generated, generic corpus of **63,880 real names** (39,749 girl / 24,131 boy)
from the SSA's public baby-name archive — every spelling with at least 25
recorded births — built at development time and committed as a source module.
Within it, a **core** of the most currently-used names (7,457 girl / 5,707 boy)
is dealt first in popularity-weighted random order, so early cards are familiar
while the long tail stays reachable. Everything else about
swiping stays as-is: the same fixed-seed shuffle keeps both swipers on the same
path, and picks stay keyed by name so no storage migration is needed.

The one real code change beyond the data swap: matches and keeps are currently
derived by filtering the *active pool* (`BabyNameSwipe.tsx:450` and `:521`), so
any previously kept name that doesn't survive corpus curation would silently
vanish from the Matches screen. Both lists move to deriving from `picks`, which
is the authoritative record of what the user actually swiped.

## Technical Context

**Language/Version**: TypeScript ~6.0 / React 19, ES modules; corpus build
script is plain Node 20+ (`.mjs`, no new dependencies)

**Primary Dependencies**: none added. Vite 8 + React 19 as today; the corpus is
a committed source module, not a runtime fetch

**Storage**: unchanged — single `localStorage` key `babyname-swipe-v3` via the
`window.storage` shim. No schema change: `picks` is already keyed by name
string, so a larger pool needs no migration

**Testing**: repo has no test framework (`npm run lint` = oxlint, `npm run
build` = tsc + vite). Verification is a dependency-free
`scripts/verify-name-corpus.mjs` invariant checker plus the manual scenarios in
[quickstart.md](quickstart.md)

**Target Platform**: mobile-first browsers, iOS Safari primary

**Project Type**: single-page web app (static, no backend)

**Performance Goals**: swipe response unchanged; app start adds ≤ ~200 ms on a
mid-range phone; swiper/filter switch stays under ~150 ms (spec SC-004). At
this corpus size these are the binding constraints, and they require the
load-path work in research Decision 2b — not free by default

**Constraints**: corpus adds ~217 KB gzip (bundle 70 KB → 292 KB); zero runtime
network calls; zero recurring cost; no visual or interaction changes

**Scale/Scope**: 63,880 names (39,749 girl / 24,131 boy; core 7,457 / 5,707),
verified against the live SSA archive, vs. 800 today; two touched source files
plus build/verify/validate scripts and one generated module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Verdict |
|---|---|---|
| I. Muted Visual Design | No UI, palette, or motion changes; card rendering untouched (`g` tag still drives the band color) | PASS |
| II. Cost Consciousness | Corpus is generated at development time and committed; zero runtime services, zero metered calls, no new hosting cost | PASS |
| III. Pipeline-Only Deployments | No workflow changes; the generated module is ordinary committed source that deploys through the existing pipeline. Corpus verification is a local npm script, deliberately not wired into the deploy workflows so SHA stamping stays untouched | PASS |
| IV. Storage Key Stability | `STORAGE_KEY` untouched and no schema change — `picks` is keyed by name, so growing the pool orphans nothing. The FR-006 fix strictly *increases* what survives (names dropped from the pool keep their keeps/matches) | PASS |

Additional constraints: no backend introduced; mobile hardening untouched; the
name-pool invariants that still apply (single gender per spelling, no
girl/boy overlap, deterministic shared ordering) are enforced by the verify
script. The old stylistic rules (no D-starts, no -y/-ie/-ey endings) are
retired by explicit decision in the spec.

**Post-Phase-1 re-check**: still PASS. The design adds no runtime dependency,
no persisted schema change, and no UI surface.

## Project Structure

### Documentation (this feature)

```text
specs/001-expanded-name-corpus/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — sourcing decisions, measured sizes
├── data-model.md        # Phase 1 output — corpus + derivation model
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/
│   └── name-corpus.md   # Phase 1 output — module + derivation contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
scripts/
├── build-name-corpus.mjs    # NEW: fetch + curate + emit the corpus module
└── verify-name-corpus.mjs   # NEW: dependency-free invariant checks

src/
├── BabyNameSwipe.tsx        # MODIFIED: import corpus; derive matches/keeps from picks
├── lib/
│   ├── nameCorpus.ts        # NEW (generated, committed): the name data
│   ├── storage.ts           # unchanged
│   └── useUpdateCheck.ts    # unchanged
└── App.tsx                  # unchanged
```

**Structure Decision**: Keep the app's existing shape — one screen component
plus small standalone modules under `src/lib/`. The corpus goes in
`src/lib/nameCorpus.ts` alongside the other standalone pieces rather than
inline in `BabyNameSwipe.tsx`, because it is machine-generated and would
otherwise bury the component under thousands of lines. Build tooling lives in a
new top-level `scripts/` directory (no such directory exists today) since it
runs at development time, never in the app or the deploy pipeline.

## Key Design Decisions

1. **Generated-and-committed, not fetched.** The corpus ships as source. This
   keeps the app offline-capable and free (Constitution II), and keeps deploys
   reproducible (Constitution III).

2. **Rank is array position.** Names are emitted ordered by descending
   popularity (births since 1995), so index *is* the popularity rank. FR-001's
   "popularity retained for later features" costs zero extra bytes, and spec
   003 can use it directly for "common but not top-10" criteria — which at this
   corpus size is the main lever for taming deck quality.

2b. **Corpus size and deck feel are separate knobs.** A 25-birth floor removes
   the source's one-off spellings (105,966 → 63,880) without curating toward
   "good" names, and a core-first, popularity-weighted deal decides what the
   first cards look like. Shipping everything with a flat shuffle was tried and
   rejected in use — see research Decision 2.

2c. **The load path is paid for deliberately.** Three mitigations are part of
   this feature, not follow-ups — pack the corpus as delimited strings rather
   than array literals, keep pools as plain string arrays (materialize
   `{ n, g }` only for visible cards), and build only the active gender
   filter's pool instead of all three eagerly. Measured result: +126 ms to
   first card at 4× CPU throttle, inside the 200 ms budget.

3. **The `s` (style) tag is dropped.** It is referenced nowhere in the codebase
   and cannot be derived for a generic corpus. `g` (girl/boy) stays — it drives
   the card band color.

4. **Matches and keeps derive from `picks`, not from the pool.** This is the
   FR-006 fix. `ListView`'s `Row` renders only the name string, so no gender
   lookup is needed to display them. Scoping rule: names known to the corpus are
   filtered by the active girl/boy/both view exactly as today; names *not* in
   the corpus (legacy picks) are always shown, since hiding them is the data
   loss the requirement exists to prevent.

5. **List ordering becomes chronological.** Today matches/keeps inherit the
   shuffled pool's arbitrary order; deriving from `picks` yields swipe order.
   This is a deliberate, minor improvement, not a regression.

6. **No storage migration code.** Verified against the current shape: `picks`
   is keyed by name string and nothing persists deck positions, so a bigger
   pool needs no migration at all. The only behavioral guard needed is decision
   4.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
