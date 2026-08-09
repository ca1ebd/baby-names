# Data Model: Expanded Name Corpus

**Phase 1 output** — entities, validation rules, and what changes vs. today.

## Entity: Name Corpus (new, generated)

The bundled list of real names, emitted by `scripts/build-name-corpus.mjs` into
`src/lib/nameCorpus.ts` and committed.

| Field | Type | Notes |
|---|---|---|
| `GIRL_CORPUS` | `string[]` | 66,188 girl-assigned spellings, index = popularity rank (0 = most popular) |
| `BOY_CORPUS` | `string[]` | 39,778 boy-assigned spellings, same ordering rule |

**Storage form**: each list is emitted as a single comma-delimited string literal
and `.split(",")` at module load, not as a 100k-element array literal — this
parses substantially faster and drops the per-name quote bytes (research
Decision 2b). The exported type stays `string[]`, so consumers are unaffected.

**Validation rules** (enforced by `scripts/verify-name-corpus.mjs`):

- Every entry matches `/^[A-Z][A-Za-z'-]{1,14}$/` — title-cased, 2–15 chars,
  letters plus internal hyphen/apostrophe only.
- No duplicates within either array.
- `GIRL_CORPUS ∩ BOY_CORPUS = ∅` — the no-overlap invariant that makes
  name-keyed picks safe in "both" mode (spec FR-001).
- Both arrays are non-empty and meet their expected magnitude (≈66k girl /
  ≈40k boy; the verifier warns on a >10% swing, which signals a source or
  parsing regression rather than a legitimate data update).
- Arrays are ordered by descending source popularity (verified by the script
  emitting a rank-ordered file; not re-derivable at runtime).

**Derived per active filter** (in `BabyNameSwipe.tsx`, replacing today's `RAW`):

- `poolFor("girl")` → `shuffled(GIRL_CORPUS)` (strings)
- `poolFor("boy")` → `shuffled(BOY_CORPUS)`
- `poolFor("both")` → `shuffled([...GIRL_CORPUS, ...BOY_CORPUS])`

Two changes from today, both from research Decision 2b: pools hold **name
strings**, not `{ n, g }` objects (gender is recovered from corpus membership,
and the object is built only for the few visible cards), and pools are built
**lazily per filter and memoized** rather than all three eagerly at module
load.

The `shuffled()` helper and its fixed seed (`20260730`) are unchanged — this is
what keeps both swipers on the same order with no bookkeeping (spec FR-004).

## Entity: Name Card (modified)

The per-name object the swipe UI consumes.

| Field | Type | Change |
|---|---|---|
| `n` | `string` | unchanged — the spelling; also the `picks` key |
| `g` | `"girl" \| "boy"` | unchanged — drives the card band color |
| `s` | ~~`"c" \| "u"`~~ | **removed** — the style tag is referenced nowhere in the codebase and cannot be derived for a generic corpus |

## Entity: Persisted State (unchanged)

No schema change and no migration code. The stored object keeps its exact
shape under the unchanged key `babyname-swipe-v3`:

```
{
  people: [{ label, picks: { [name]: "keep" | "no" } }, { ... }],
  lastName, genderFilter, onboarded
}
```

Because `picks` is keyed by name string and nothing persists deck positions,
growing the pool orphans nothing (spec FR-005). Names in `picks` that are
absent from the new corpus simply never get dealt again — but they remain
visible per the derivation change below.

## Derivation change: matches and keeps

**Today** (`BabyNameSwipe.tsx:450`, `:521`) — both derived from the active pool,
so a name absent from the pool is invisible even if the user swiped it:

```
matches = pool.filter(x => a.picks[x.n] === "keep" && b.picks[x.n] === "keep")
keeps   = pool.filter(x => picks[x.n] === "keep")
```

**New** — derived from `picks`, which is the authoritative record of what the
user actually swiped (spec FR-006):

- `keeps`: the current swiper's `picks` entries valued `"keep"`, in insertion
  (swipe) order.
- `matches`: names where *both* people's `picks` are `"keep"`, in insertion
  order.
- **Filter scoping**: a name found in the corpus is shown only when its gender
  matches the active girl/boy/both view (today's behavior); a name *not* in the
  corpus is shown in every view, because hiding it is exactly the data loss
  FR-006 exists to prevent.

A corpus membership lookup (`name → "girl" | "boy" | undefined`) built once at
module load supports the scoping test. `ListView`'s `Row` renders only the name
string, so no gender data is needed for display.

**Ordering note**: matches and keeps currently inherit the shuffled pool's
arbitrary order; deriving from `picks` yields chronological swipe order — a
deliberate minor improvement (plan Decision 5).

## State transitions

None. This feature introduces no new states, screens, or lifecycle behavior;
the deck/undo/match flows are untouched.
