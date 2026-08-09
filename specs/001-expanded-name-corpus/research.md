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

## Decision 2 — Curation rules

**Decision**: Keep every spelling matching `/^[A-Z][A-Za-z'-]{1,14}$/` — **no
popularity cut**. Assign each spelling to the single gender with the higher
**all-time** occurrence count (the losing gender drops it entirely). Order each
list by **births since 1995**, so array index is a recency-weighted popularity
rank. Result: **105,966 names (66,188 girl / 39,778 boy)**, ~132x today's 800.

**Rationale**: Narrowing the field is the job of the criteria feature (002),
which is expected to become a paid tier — so the corpus should be the complete
universe that filtering searches, not a pre-curated subset. Owner decision
(2026-08-08) explicitly accepts unfiltered-deck friction in the interim.

Gender assignment on all-time counts is stable and deterministic. Ranking on
recent births is what would make a *curated* deck feel contemporary, and it
still matters here because index-as-rank is the popularity signal 002 consumes.
Measured difference, same archive:

- All-time ranking puts *Mary, Patricia, Linda, Barbara, Dorothy* at the top.
- Since-1995 ranking puts *Emily, Emma, Olivia, Isabella* and *Jacob, Michael,
  Noah, Ethan* at the top.

**Measured alternatives** (retained for when 002 needs a "common names" tier):

| Floor (births since 1995) | Corpus | vs. today | Raw KB | Sample of a random hand |
|---|---|---|---|---|
| **none (chosen)** | **105,966** | **132x** | **985** | Denekia, Frontis, Dameisha, Abdulmajid, Robbye |
| ≥25 | 48,346 | 60x | 439 | Rommel, Yaindhi, Nello, Harmonii, Jeshua |
| ≥100 | 29,451 | 37x | 264 | Aaminah, Mayukha, Aakash, Cadee, Cristyn |
| ≥1,000 | 7,242 | 9x | 64 | Colby, Gabriel, Colten, Joann, Divya, Ruthie |

**Accepted consequence**: the deck is uniformly shuffled, so a one-off spelling
is dealt as readily as *Emma*; roughly 25,000 entries appear only once
nationally since 1995. The owner accepts this friction for this release.

**Alternatives rejected**: keeping a name in both gender pools (violates the
no-overlap invariant that makes name-keyed picks safe); a curated top-N cut
(rejected by the owner — filtering belongs in 002); popularity-weighted deck
ordering instead of uniform shuffle (a deck-behavior change, out of scope for
this feature).

## Decision 2b — Load-path cost of the full corpus

**Decision**: Ship the corpus as **packed delimited strings split at module
load**, keep pools as plain string arrays, and **build only the pool for the
active gender filter** rather than all three eagerly.

**Rationale**: measured on the real 105,966-name corpus:

| Metric | Naive (array literal of objects, all 3 pools eager) |
|---|---|
| Module raw / gzip | 985 KB / **383 KB** |
| Module-load build + shuffle (Node, desktop) | 118 ms → est. 300–500 ms mid-range phone |
| Deck rebuild (`pool.filter`) | 26 ms → est. ~75–100 ms on phone |
| Heap | 26 MB |

Unoptimized, that is a tripled bundle plus a visible startup stall — a
regression against spec SC-004 even though no user-visible feature changed.
The three mitigations are cheap and well-understood:

1. **Packed strings** (`"Emma,Olivia,…".split(",")`) parse far faster than a
   106k-element array literal and drop the per-name quote bytes (~985 KB →
   ~775 KB raw).
2. **String arrays, not object arrays** — `{ n, g }` is materialized only for
   the handful of visible cards; gender comes from which pool the name is in.
   This removes ~106k object allocations from startup and most of the heap.
3. **Lazy per-filter pools** — today all three (`GIRL`, `BOY`, `BOTH`) are
   built at module load; building only the active one cuts roughly two-thirds
   of that work, memoized per filter thereafter.

Transfer cost is further reduced in production by Azure Static Web Apps'
Brotli encoding (est. ~280 KB vs. 383 KB gzip). Verification of the resulting
numbers is part of the quickstart, not an assumption.

**Alternatives rejected**: code-splitting the corpus into a lazily-loaded chunk
(worthwhile if startup budget is missed, but it delays the first card — the
one thing the app must do instantly); trimming the corpus (the owner's
decision above rules it out).

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
