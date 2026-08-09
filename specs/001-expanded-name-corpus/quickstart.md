# Quickstart: Validating the Expanded Name Corpus

Runnable checks that prove the feature works end to end. No test framework is
installed in this repo, so validation is a mix of scripted invariant checks and
short manual scenarios in the browser.

## Prerequisites

```bash
npm ci
```

**Shortcut**: scenarios §2b, §3, §4, §5 and §6 below are automated in
`scripts/validate-corpus-ui.mjs`, which drives a real Chromium. Playwright is
not a project dependency, so install it only when running the check:

```bash
npm install --no-save playwright
npm run build && npm run preview -- --port 4173 &
node scripts/validate-corpus-ui.mjs        # 13 checks
```

The manual steps below remain the source of truth for what is being verified,
and §7 (real iOS device) can only be done by hand.

Corpus generation needs network access to the chosen source. `ssa.gov` is
blocked by this environment's network policy today; the `mirror` source
(raw.githubusercontent.com) is reachable. See research Decision 1.

## 1. Generate and verify the corpus

```bash
node scripts/build-name-corpus.mjs          # defaults: --source ssa --since 1995, no cut
node scripts/verify-name-corpus.mjs
```

**Expected**: the build downloads the 7.5 MB SSA archive (146 yearly files,
1880–2025), prints per-gender counts of **66,188 girl / 39,778 boy (105,966
total)**, and writes `src/lib/nameCorpus.ts`. The verifier exits 0 with all
invariants passing: format, no commas in entries, no duplicates, no girl/boy
overlap, counts within 10% of expected.

Sanity-check the head of each list — it should read contemporary
(*Emily, Emma, Olivia, Isabella…* / *Jacob, Michael, Noah, Ethan…*), not
mid-century (*Mary, Patricia, Linda…*). Mid-century names at the top mean the
ranking fell back to all-time counts instead of `--since`.

A 403 from ssa.gov means the browser header set is missing or incomplete (see
[contracts/name-corpus.md](contracts/name-corpus.md)), not that the network is
blocked. `--source mirror` is the offline fallback.

A verifier failure must block the change — it means the corpus violates the
guarantees in [contracts/name-corpus.md](contracts/name-corpus.md).

## 2. Build and lint

```bash
npm run lint
npm run build
```

**Expected**: both pass. Record the corpus chunk's gzip size from Vite's build
output — the unoptimized baseline is 383 KB, and the packed-string form should
come in meaningfully under it. Azure Static Web Apps serves Brotli, so the
over-the-wire figure is lower again (~280 KB at the baseline).

## 2b. Performance budget (spec SC-004)

At 105,966 names the load path is the risk, not the swipe path. Measured
baselines on desktop Node with a naive object-array implementation: 118 ms
module-load build+shuffle, 26 ms per deck rebuild, 26 MB heap.

Check in the browser with devtools CPU throttling at 4x:

1. Cold load → first card visible. **Expected**: no more than ~200 ms added
   versus the pre-change build.
2. Toggle the gender filter and switch swipers. **Expected**: under ~150 ms,
   no dropped-frame stutter on the segmented control.
3. Swipe 20 cards rapidly. **Expected**: identical feel to today — the swipe
   path touches only the visible cards and must not regress.

If any budget is missed, the mitigations in research Decision 2b (packed
strings, string-not-object pools, lazy per-filter pools) are the levers;
trimming the corpus is not, by owner decision.

## 3. Fresh-install scenario (spec User Story 1)

```bash
npm run dev
```

In a browser with empty storage:

1. Complete onboarding, choose **girl**, swipe ~20 cards.
   **Expected**: real names, correct pink band, no repeats.
2. Switch the filter to **boy**, then **both**.
   **Expected**: appropriate names per mode; neutral slate band in "both" mode.
3. Swipe past 800 cumulative names (or inspect the pool length in devtools).
   **Expected**: the deck keeps going well past the old 800-name pool.

## 4. Shared-order scenario (spec FR-004 / SC-003)

1. As swiper A, swipe 20 names and note them in order.
2. Switch to swiper B via the segmented control and swipe 20.

**Expected**: B sees the same 20 names in the same order. Neither swiper is
re-served a name they already swiped.

## 5. Upgrade scenario — the critical one (spec User Story 2 / SC-002)

This is the regression the feature exists to avoid. Seed a pre-upgrade save
that contains a name **deliberately absent from the new corpus**:

1. On the *current* build, swipe as both swipers so at least one name is kept
   by both (a match) and one is kept by a single swiper.
2. Use **Copy Backup** to capture the state, or note the storage contents.
3. Switch to the new build, restore/reload that state.
4. Open the Matches screen.

**Expected**: every prior match and keep is still listed — including any name
that is not in the new corpus. Profile fields (names, last name, filter) are
unchanged. Nothing forces re-onboarding.

To construct the absent-name case deterministically, add a nonsense entry
directly to `picks` for both people (e.g. `"Zzyzxia": "keep"`) before step 3;
it must still appear under "Both said yes" afterward.

## 6. Storage safety check (Constitution IV)

In devtools, confirm the save is still under `babyname-swipe-v3` with the same
shape (`people` / `lastName` / `genderFilter` / `onboarded`) and that no new
top-level keys appeared.

## 7. Staging verification

Push the branch; the staging workflow deploys to
`https://baby-names.test.calebdudley.dev`. Repeat scenarios 3–5 on a real iOS
device — the layout is unchanged, so this is a smoke test rather than a full
pass.
