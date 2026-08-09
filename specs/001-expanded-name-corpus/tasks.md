---

description: "Task list for Expanded Name Corpus"
---

# Tasks: Expanded Name Corpus

**Input**: Design documents from `/specs/001-expanded-name-corpus/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/name-corpus.md](contracts/name-corpus.md), [quickstart.md](quickstart.md)

**Tests**: No test framework exists in this repo and none was requested, so
there are no test-authoring tasks. Verification is the dependency-free
invariant checker (`scripts/verify-name-corpus.mjs`, a contract deliverable —
not a test suite) plus the manual scenarios in [quickstart.md](quickstart.md).

**Organization**: Tasks are grouped by user story. Both stories are P1 and both
edit `src/BabyNameSwipe.tsx`, so they are sequential rather than parallel — see
Dependencies.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Include exact file paths in descriptions

## Path Conventions

Single project at repository root: app code in `src/`, new build tooling in
`scripts/`. No `tests/` directory exists or is created.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Make room for build tooling without touching app behavior

- [X] T001 Create `scripts/` directory at repository root (does not exist yet) and add npm scripts `corpus:build` and `corpus:verify` to `package.json`
- [X] T002 [P] Add the corpus working directory (downloaded SSA archive) to `.gitignore` so the 7.5 MB `names.zip` is never committed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Produce and validate the corpus data both user stories consume

**⚠️ CRITICAL**: No user story work can begin until `src/lib/nameCorpus.ts` exists and verifies clean

- [X] T003 Implement `scripts/build-name-corpus.mjs` per [contracts/name-corpus.md](contracts/name-corpus.md) §2: flags `--source ssa|mirror`, `--input`, `--limit`, `--since` (default 1995), `--out`; download SSA `names.zip` **with the full browser header set** (`User-Agent`, `Accept`, `Accept-Language`, `Sec-Fetch-*`, `Upgrade-Insecure-Requests`, `sec-ch-ua*`, `Referer`) or Akamai returns 403; on 403 emit an error saying it is edge filtering, not a network-policy denial
- [X] T004 In `scripts/build-name-corpus.mjs`, implement parsing and curation per [research.md](research.md) Decision 2: keep spellings matching `/^[A-Z][A-Za-z'-]{1,14}$/`, assign each to the single gender with the higher **all-time** count, order each list by **births since `--since`**, apply no cut by default
- [X] T005 In `scripts/build-name-corpus.mjs`, emit `src/lib/nameCorpus.ts` in the packed form from [data-model.md](data-model.md) — two comma-delimited string literals `.split(",")` into `GIRL_CORPUS` / `BOY_CORPUS`, with a header comment recording source, generation date, and counts; exit non-zero on any invariant violation so a bad corpus is never written
- [X] T006 [P] Implement `scripts/verify-name-corpus.mjs` asserting every guarantee in [contracts/name-corpus.md](contracts/name-corpus.md) §1: entry format, no commas in entries, no duplicates within a list, empty girl/boy intersection, counts within 10% of ≈66,188 girl / ≈39,778 boy; exit non-zero on failure
- [X] T007 Run `node scripts/build-name-corpus.mjs` to generate `src/lib/nameCorpus.ts` and commit the generated module (depends on T003–T005)
- [X] T008 Run `node scripts/verify-name-corpus.mjs` and confirm it exits 0; spot-check that each list's head reads contemporary (*Emily, Emma, Olivia…* / *Jacob, Michael, Noah…*), not mid-century (*Mary, Patricia, Linda…*), which would mean ranking fell back to all-time counts (depends on T006, T007)

**Checkpoint**: Corpus data exists and satisfies its contract — app wiring can begin

---

## Phase 3: User Story 1 - A much bigger, generic default deck (Priority: P1) 🎯 MVP

**Goal**: The deck deals from all 105,966 corpus names instead of the 800-name hand-built pool, with no visual or interaction change and no startup regression.

**Independent Test**: On a fresh install, swipe past 800 cumulative names and confirm real, correctly gender-tagged names keep coming with no repeats; both swipers encounter the same order.

### Implementation for User Story 1

- [X] T009 [US1] In `src/BabyNameSwipe.tsx`, delete the `RAW` literal (lines ~8–20) and import `GIRL_CORPUS` / `BOY_CORPUS` from `./lib/nameCorpus`
- [X] T010 [US1] In `src/BabyNameSwipe.tsx`, rewrite the pool construction so pools hold **name strings** rather than `{ n, s, g }` objects, and build each gender's shuffled pool **lazily on first use and memoize it** instead of building `GIRL_NAMES`, `BOY_NAMES`, and `BOTH_NAMES` eagerly at module load (research Decision 2b); keep `shuffled()` and its seed `20260730` unchanged so both swipers still share one order
- [X] T011 [US1] In `src/BabyNameSwipe.tsx`, update `poolFor()` and every pool consumer (`deck` at ~line 437, `visible` at ~line 522, the `Card` render path) to work with string pools, materializing the `{ n, g }` card object only for the visible cards; derive `g` from which corpus list contains the name
- [X] T012 [US1] In `src/BabyNameSwipe.tsx`, remove all remaining references to the retired `s` (style) tag, confirming via search that nothing consumes it
- [X] T013 [US1] Run `npm run lint` and `npm run build`; then in the browser confirm swiping, the girl/boy/both filter, card band colors (pink / blue / neutral slate in "both"), and undo all behave exactly as before

**Checkpoint**: The bigger deck works end to end; matches/keeps still use the old pool-filtered derivation and are fixed next

---

## Phase 4: User Story 2 - Existing users upgrade without losing anything (Priority: P1)

**Goal**: Keeps and matches reflect what users actually swiped, including names absent from the new corpus — the data-loss regression this feature exists to prevent.

**Independent Test**: Seed a save containing a name deliberately absent from the corpus (e.g. `"Zzyzxia": "keep"` for both people), load the new build, and confirm it still appears under "Both said yes".

### Implementation for User Story 2

- [X] T014 [US2] In `src/lib/nameCorpus.ts` consumers (or a small helper beside them), build a memoized corpus membership lookup `name → "girl" | "boy" | undefined`, used only for filter scoping — not for rendering
- [X] T015 [US2] In `src/BabyNameSwipe.tsx`, replace the `keeps` derivation (currently `pool.filter(...)` at ~line 521) with one derived from the current swiper's `picks` entries valued `"keep"`, in insertion order
- [X] T016 [US2] In `src/BabyNameSwipe.tsx`, replace the `matches` derivation (currently `pool.filter(...)` at ~line 450) with one derived from both people's `picks`, keeping names where both are `"keep"`, in insertion order
- [X] T017 [US2] Apply the scoping rule from [data-model.md](data-model.md) to both lists: a name found in the corpus shows only when its gender matches the active girl/boy/both view; a name **not** in the corpus shows in every view
- [X] T018 [US2] Execute [quickstart.md](quickstart.md) §5 (upgrade scenario) with a seeded absent name and confirm every prior match and keep survives, profile fields are unchanged, and no re-onboarding is triggered
- [X] T019 [US2] Execute [quickstart.md](quickstart.md) §6: confirm the save is still under `babyname-swipe-v3` with an unchanged shape and no new top-level keys (Constitution IV)

**Checkpoint**: Both user stories complete; the feature is functionally done

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Confirm the performance budget the full corpus put at risk, and correct now-stale documentation

- [X] T020 Execute [quickstart.md](quickstart.md) §2b with 4x CPU throttling: cold load adds ≤ ~200 ms, swiper/filter switch under ~150 ms, swipe feel unchanged (spec SC-004). Baselines to beat: 118 ms module-load and 26 ms deck rebuild measured on the naive implementation
- [X] T021 Record the corpus chunk's gzip size from the `npm run build` output and compare against the 383 KB unoptimized baseline; if the budget in T020 is missed, apply the research Decision 2b levers — trimming the corpus is explicitly not an option
- [X] T022 [P] Update `CLAUDE.md`: the "Name pools" section still describes the retired `RAW` structure, the `c`/`u` style tags, the no-D-starts / no-"ey"-endings rules, and the 800-name pool — replace with the generated corpus, its size, and the build/verify scripts
- [X] T023 [P] Update `CLAUDE.md` "Data model & storage" to note that keeps and matches now derive from `picks` rather than the active pool, and why (names absent from the corpus must stay visible)
- [X] T024 Execute the remaining [quickstart.md](quickstart.md) scenarios (§3 fresh install, §4 shared order) end to end
- [ ] T025 Push the branch and verify the staging deploy at `https://baby-names.test.calebdudley.dev` on a real iOS device — layout is unchanged, so this is a smoke test of load time and swipe feel on real hardware

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup; **blocks both user stories** — no app wiring is possible before `src/lib/nameCorpus.ts` exists
- **User Story 1 (Phase 3)**: depends on Phase 2
- **User Story 2 (Phase 4)**: depends on Phase 2. Technically independent of US1 in logic, but **must follow US1 in practice** because both edit `src/BabyNameSwipe.tsx` and US1 rewrites the pool representation that US2's scoping rule reads
- **Polish (Phase 5)**: depends on both stories

### Within Each Phase

- T003 → T004 → T005 are sequential (same file, layered behavior)
- T007 depends on T003–T005; T008 depends on T006 + T007
- T009 → T010 → T011 → T012 are sequential (same file, same region)
- T014 → T015/T016 → T017 (lookup before consumers; scoping after both derivations exist)

### Parallel Opportunities

Genuinely parallel work is limited — this feature concentrates in one component file plus two scripts:

- **T002** (`.gitignore`) alongside T001
- **T006** (`scripts/verify-name-corpus.mjs`) alongside T003–T005 (`scripts/build-name-corpus.mjs`) — different files, no shared state
- **T022 and T023** (both `CLAUDE.md`, different sections) can be done together in one pass

Everything touching `src/BabyNameSwipe.tsx` (T009–T012, T015–T017) is strictly sequential.

---

## Parallel Example: Phase 2

```bash
# The two scripts are independent files and can be written concurrently:
Task: "Implement scripts/build-name-corpus.mjs (T003–T005)"
Task: "Implement scripts/verify-name-corpus.mjs (T006)"

# Then converge:
Task: "Generate the corpus (T007), then verify it (T008)"
```

---

## Implementation Strategy

### MVP scope

**Phases 1–3 (T001–T013)** deliver the MVP: the app deals from the full corpus
with unchanged look and feel. It is demoable and deployable at that checkpoint.

However, **do not ship the MVP to production alone.** User Story 2 is also P1
because without it the corpus swap silently drops keeps and matches for names
that fall outside the new list — the exact data loss the spec calls
unrecoverable. Treat T001–T019 as the shippable unit; T013's checkpoint is an
internal validation gate, not a release gate.

### Incremental delivery

1. Phases 1–2 → corpus generated and verified, app untouched, nothing to break
2. Phase 3 → bigger deck working (validate on staging)
3. Phase 4 → upgrade safety restored → **release candidate**
4. Phase 5 → performance budget confirmed and docs corrected → ship

### Notes

- Commit after each task or logical group; the generated corpus module lands in its own commit (T007) so the data change is reviewable apart from the code change
- The 7.5 MB SSA archive is never committed — only the generated module
- Stop at any checkpoint to validate independently
