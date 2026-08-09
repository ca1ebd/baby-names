# Research Notes: Expanded Name Corpus

**Created**: 2026-08-08 (Phase 0 of `/speckit-plan`; extends the pre-planning
sourcing note)

## Decision 1 — Corpus source

**Decision**: Generate the corpus from U.S. Social Security Administration
baby-name data. Primary source is SSA's own bulk download; a public
SSA-derived GitHub mirror is the documented fallback and is what this
environment can actually reach today.

**Rationale**: SSA data is the standard reference for U.S. given names, is a
U.S. government work in the public domain (no attribution or licensing
constraints on a derived list bundled in the app), carries occurrence counts
(which give both popularity ranking and a deterministic girl/boy assignment),
and consists only of names real people were actually given — satisfying the
spec's "real names only" requirement by construction.

**Sources evaluated, with measured results**:

| Source | Reachable from this environment | Coverage | Distinct names |
|---|---|---|---|
| `ssa.gov/oact/babynames/names.zip` (authoritative) | **Yes** — verified, 7.5 MB downloaded | 1880–2025 (146 yearly files), all names ≥5 occurrences/year | 105,966 raw → 66,188 girl / 39,778 boy after validity + gender assignment |
| `hadley/data-baby-names` CSV via raw.githubusercontent.com | Yes | 1880–2008, top 1000/year/sex | 6,782 (3,750 girl / 3,032 boy) |
| `aruljohn/popular-baby-names` JSON via raw.githubusercontent.com | Yes | 2009–2024, top 1000/year/sex, rank only | 1,502 girl / 1,416 boy |
| Union of the two mirrors | Yes | 1880–2024 | 7,358 (4,063 girl / 3,295 boy) |
| `names-dataset` (PyPI, 54 MB) | Yes | global, social-media-derived | rejected — provenance is scraped social data, not birth records |

**Resolution**: use the authoritative SSA archive. The mirrors are retained in
the build script only as an offline/CI-free fallback.

**Access note (important for the build script)**: SSA is fronted by Akamai,
which returns HTTP 403 to plain `curl`/default agents — including for ordinary
HTML pages. Requests succeed with a full browser header set (browser
`User-Agent`, `Accept`, `Accept-Language`, `Sec-Fetch-*`,
`Upgrade-Insecure-Requests`, `sec-ch-ua*`). The build script must send these
headers or it will fail with a 403 that looks like a network-policy denial but
is not.

**Alternatives rejected**: AI-generated name lists (the spec requires real
names, and generation cost recurs — Constitution II); Kaggle mirrors (require
authentication); `names-dataset` (provenance unsuitable for a baby-name app).

## Decision 2 — Curation rules and deck shaping

**Decision**: Three settings, tuned against the real archive:

| Setting | Value | Effect |
|---|---|---|
| Full-list floor | ≥ 25 all-time births | 105,966 → **63,880** (39,749 girl / 24,131 boy) |
| Core membership | ≥ 300 births since 2005 | **7,457 girl / 5,707 boy** |
| Core ordering | births since 2005, descending | index = "familiar today" rank |

Gender assignment still uses all-time counts (stable, deterministic). The deck
deals the **core first, in a popularity-weighted random order**, then the long
tail shuffled flat.

**Rationale**: the first cut shipped every spelling SSA publishes, and in use
that read as noise — a random hand was *Denekia, Frontis, Dameisha, Robbye*.
Two separate problems hid in that, and they need separate fixes:

1. **The floor was too low.** SSA's own cutoff is 5 occurrences in a single
   year, which admits ~42,000 spellings used once nationally. A 25-use
   all-time floor removes that noise without curating toward "good" names.
2. **A flat shuffle buries the familiar names.** Even with a decent corpus, a
   uniform draw from 7,457 core names has median rank ~3,700 — so *Emma* is as
   rare as *Zalayah*. Corpus size and deck feel are independent knobs, and
   only the second one controls what the first twenty cards look like.

**Deck-shaping options measured** (median popularity rank of the first 20
cards, girl core):

| Ordering | Median rank | Reads as |
|---|---|---|
| Strict popularity | ~10 | a top-100 list; no discovery |
| Flat shuffle | 2,756 | mostly unrecognizable |
| Weighted, `u^((rank+1)^0.7)` | 860 | still ~9 of 24 from beyond rank 2,000 |
| **Weighted, `u^(rank+1)`** | **182** | **familiar, ~1 card in 6 from deeper** |

The chosen scheme is weighted sampling without replacement (Efraimidis–Spirakis):
each name draws `key = u^(rank+1)`, highest keys deal first. Nothing is
excluded — a rank-7,000 name can still surface early, just rarely. Because the
weight comes from array position and the lists are already rank-ordered, this
costs **zero extra bytes**; storing per-name weights was considered and
rejected for that reason.

Observed first cards after tuning: *Alannah, Josephine, Olivia, Kylie, Sloane,
Josephina, Favour, Sloan, Emma, Makena* (girl) and *Antonio, Jacob, Elias,
Donovan, Kashmir, Flynn, Noah, Fox, Brennan, Max* (boy).

**Retained for spec 002**: the core/tail boundary is exactly the "common names"
tier a criteria filter wants for "common but not top-10" style requests.

**Alternatives rejected**: keeping a name in both gender pools (breaks the
no-overlap invariant that makes name-keyed picks safe); curating the corpus
down to a hand-picked list (the owner's decision stands — narrowing is 002's
job, and the tail stays reachable); ranking the core by all-time or since-1995
counts (surfaces *Mary, Patricia, Linda* and other names no longer in use).

## Decision 2b — Load-path cost

**Decision**: Ship the corpus as **packed delimited strings split at module
load**, keep pools as plain string arrays, and **build only the pool for the
active gender filter** rather than all three eagerly.

**Rationale**: a naive implementation of the first (105,966-name) cut measured
985 KB raw / 383 KB gzip, 118 ms of module-load work on desktop Node
(est. 300–500 ms on a mid-range phone), 26 ms per deck rebuild and 26 MB heap —
a tripled bundle and a visible startup stall, a regression against SC-004 with
no user-visible feature to justify it. The three mitigations:

1. **Packed strings** (`"Emma,Olivia,…".split(",")`) parse far faster than a
   tens-of-thousands-element array literal and drop the per-name quote bytes.
2. **String arrays, not object arrays** — `{ n, g }` is materialized only for
   the handful of visible cards; gender comes from a membership set built on
   first use, so a fresh swiper never pays for it.
3. **Lazy per-filter pools** — only the active filter's pool is ever built,
   memoized thereafter.

**Measured, final** (63,880-name corpus, all mitigations in place):

| Metric | Baseline (800-name pool) | Shipped |
|---|---|---|
| Bundle, gzip | 70 KB | 292 KB (corpus module 217 KB of it) |
| Cold load → first card, 4× CPU throttle | 242 ms | **368 ms (+126 ms)** |
| Budget (spec SC-004) | — | ≤ 200 ms added ✅ |

Azure Static Web Apps serves Brotli, so the over-the-wire figure is lower again.

**Alternatives rejected**: code-splitting the corpus into a lazily-loaded chunk
(worthwhile if the budget is ever missed, but it delays the first card — the
one thing the app must do instantly).

## Decision 3 — Artifact format and delivery

**Decision**: The build script emits `src/lib/nameCorpus.ts` — two exported
arrays of plain strings ordered by rank — and the file is committed to the
repo. The script is `scripts/build-name-corpus.mjs`, plain Node with no new
dependencies, run manually by a developer, never by CI.

**Rationale**: A committed static module keeps runtime cost at zero
(Constitution II), keeps the app fully offline-capable, and keeps deploys
reproducible through the existing pipeline (Constitution III) without touching
the hand-written workflows. At ~7,400 short strings the module is roughly 60 KB
raw / well under 40 KB gzipped, acceptable for a mobile-first bundle.

**Alternatives rejected**: fetching the corpus at runtime (adds a network
dependency and breaks the offline posture for a static asset); a JSON file in
`public/` (same downside, plus a second round trip); generating during CI
(would touch the deploy workflows and make builds non-reproducible).

## Decision 4 — Preserving keeps and matches (FR-006)

**Decision**: Derive matches and keeps from the `picks` records rather than by
filtering the active pool. Names present in the corpus are scoped by the active
girl/boy/both view as today; names absent from the corpus are always shown.

**Rationale**: Verified in the current code — `BabyNameSwipe.tsx:450` computes
matches as `pool.filter(both keep)` and `:521` computes keeps the same way, so
a name dropped during the pool swap disappears from the Matches screen even
though the user swiped it. `picks` is the authoritative record. `ListView`'s
`Row` renders only the name string, so switching the source needs no gender
lookup for display.

**Alternatives rejected**: guaranteeing the new corpus is a superset of the old
800 names (constrains curation forever and still breaks on any future pool
edit); shipping a legacy name→gender lookup table (unnecessary — the list rows
don't render gender).

## Sources

- [SSA Popular Baby Names — data files](https://www.ssa.gov/oact/babynames/limits.html)
- [data.gov: Baby Names from Social Security Card Applications](https://catalog.data.gov/dataset/baby-names-from-social-security-card-applications-national-data)
- [hadley/data-baby-names (SSA-derived CSV, 1880–2008)](https://github.com/hadley/data-baby-names)
- [aruljohn/popular-baby-names (SSA top-1000 by year, 2009+)](https://github.com/aruljohn/popular-baby-names)
- [hadley/babynames (R package mirror of SSA data)](https://github.com/hadley/babynames)
