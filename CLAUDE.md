# Baby Name Swipe

A two-person baby-naming app: each parent swipes through a shared name deck independently, and a "match" happens when both keep the same name. Single-page, mobile-first, no backend — everything lives in one device's browser storage.

## No AI vendor attribution (non-negotiable)

The words "Anthropic" and "Claude", any model name (Opus, Sonnet, Haiku, Fable, `claude-*`), and any AI-assistant self-attribution **must never** appear in branch names, commit messages or trailers (no `Co-Authored-By: Claude`, no `Claude-Session:`), PR/issue titles, bodies or comments, code comments, docs, or any other repo content. Name branches after the work (`expanded-name-corpus`, not `claude/...`). Write as the author, not as a tool advertising itself. If a default or harness setting would insert such text automatically, disable it (`includeCoAuthoredBy: false`); if it can't be disabled, say so rather than letting it through. The only exceptions are functional paths a tool requires to work — this file's name, `.claude/`, and spec-kit's own config keys. Never add new ones.

## Stack & hosting

- Vite + React + TypeScript, styled entirely with inline `style={}` objects (no CSS framework in practice, despite Tailwind being wired up).
- Almost the entire UI lives in one file: `src/BabyNameSwipe.tsx`. It carries `// @ts-nocheck` deliberately — it was ported as-is from a JS prototype and isn't worth retyping. Don't "fix" this by adding types unless asked.
- `src/App.tsx` is a one-line wrapper; `src/lib/` holds small standalone pieces: `storage.ts` (localStorage shim), `useUpdateCheck.ts` (update-banner polling hook), `global.d.ts` / `vite-env.d.ts` (ambient types).
- Hosted on Azure Static Web Apps (Free tier), resource group `baby-names-rg`, East US 2, on two separate SWA resources: `baby-names` (prod) and `baby-names-test` (staging). Prod is `https://baby-names.calebdudley.dev`, staging is `https://baby-names.test.calebdudley.dev`. Custom-domain DNS/TLS for both is managed centrally in the sibling `caleb-dudley-dev` repo via Terraform — see that repo's `docs/baby-names-domain-handoff.md` for the (fairly involved) history if either domain ever needs touching again.
- Deploys via `.github/workflows/azure-static-web-apps.yml` (prod, pushes to `main`) and `azure-static-web-apps-staging.yml` (staging, pushes to any other branch) — both **hand-written** (checkout → npm ci → write `public/version.json` with `github.sha` → `npm run build` with `VITE_COMMIT_SHA` env → deploy with `skip_app_build: true`), not Azure's auto-generated ones. That's intentional: it's what lets us bake the commit SHA into the bundle for the update-check feature and the About screen's build stamp.
- Every push to `main` auto-deploys to prod; every push to any other branch auto-deploys to staging (`https://baby-names.test.calebdudley.dev`). Docs-only changes (`**.md`, `.specify/`, `specs/`, `docs/`) don't trigger deploys. Don't proactively monitor deploy runs — only investigate if a deploy is suspected to have failed or the user asks.

## Data model & storage

- Everything persists under a single localStorage key, `babyname-swipe-v3` (defined as `STORAGE_KEY` — **never change this string**, it would orphan every saved swipe). Access goes through a `window.storage.get/set(key, sync)` shim (`src/lib/storage.ts`) rather than calling `localStorage` directly, a holdover from the original prototype's storage API.
- Shape of the persisted object:
  ```
  {
    people: [{ label: string, picks: { [name]: "keep" | "no" } }, { ... }],
    lastName: string,
    genderFilter: "girl" | "boy" | "both",
    onboarded: boolean,
  }
  ```
- `people[0]`/`people[1]` are "you" and "partner." `picks` is keyed by name string, not array index — so adding/removing/reordering names in the pool never orphans existing swipes.
- **Matches and keeps are derived from `picks`, not from the active pool.** They used to be `pool.filter(...)`, which meant any name missing from the pool silently vanished from the Matches screen — real data loss when the pool changed (spec 001). A swiped name the corpus no longer knows is always shown; a name the corpus *does* know is scoped to the active girl/boy/both view, as before.
- **Migration philosophy**: legacy saves (from before profiles/gender-filter existed) have no `onboarded` field. On load, if `onboarded === undefined`, the app silently backfills `onboarded: true, genderFilter: "girl", lastName: ""` and re-persists — it never forces an existing user back through onboarding. Brand-new installs get `onboarded: false`, which is what triggers the Welcome screen.
- No sync between devices/browsers. "Reset everything" (in Settings) wipes back to a fresh unboarded state on that one device.

## Name pools

- Names live in `src/lib/nameCorpus.ts` — **generated, never hand-edited**. It exports `GIRL_CORPUS` (39,749) and `BOY_CORPUS` (24,131), 63,880 real names total, derived from the SSA's public baby-name archive (1880–2025). Regenerate with `npm run corpus:build`, check invariants with `npm run corpus:verify`.
- The corpus is **generic on purpose**. The old hand-built `RAW` pool (800 names, `c`/`u` style tags, no names starting with "D" or ending in "y"/"ie"/"ey") was retired in spec 001: narrowing the deck is the job of the AI criteria filter (spec 002), not of a curated pool. Don't reintroduce build-time name rules.
- **Two knobs, don't confuse them**: `--min-uses` (default 25 all-time births) sets what's *in* the corpus — it only strips the source's one-off spellings, since SSA's own floor is 5 uses in a single year. The **core** (`--core-min`, default 300 births since `--core-since` 2005) sets what gets dealt *first*. Deck quality is an ordering problem, not a size problem; shipping all 105,966 spellings with a flat shuffle was tried and read as noise.
- Each list is **core-first**: `GIRL_CORE_SIZE` (7,457) and `BOY_CORE_SIZE` (5,707) mark the boundary. Core entries are ranked by births since 2005, the tail by births since 1995 — so an array index is a popularity rank in both parts, which spec 002 consumes for "common but not top-10" criteria.
- The deck deals the **core in a popularity-weighted random order** (`weightedShuffle`, each name drawing `key = u^(rank+1)`), then the tail flat-shuffled. Strict rank reads as a top-100 list; a flat shuffle buries Emma among thousands of rare spellings. Tuned so the median of the first 20 cards sits near rank 180 with roughly one card in six from deeper — familiar, with the occasional left-field pick. Nothing is unreachable.
- Girl and boy lists share **zero spellings** (a name is assigned to whichever gender used it more all-time). This matters because "both" mode concatenates them and picks are keyed by name alone, so a collision would let picking a name in one gender silently affect the other. `npm run corpus:verify` enforces it.
- Pools hold **plain name strings**, not `{ n, g }` objects — at this size, materializing objects for the whole pool costs startup time for no benefit. The card object is built only for the two or three visible cards; `genderOf()` resolves a name's gender from membership sets built lazily on first use (building them eagerly cost ~270ms of first paint).
- All ordering runs off one seeded PRNG (seed `20260730`) so both parents see the same deck on any device — deterministic, never `Math.random()`. Pools are built **lazily per filter and memoized**, not all three at module load.
- The corpus adds ~217 KB gzip to the bundle (70 KB → 292 KB) and ~126 ms to cold load at 4x CPU throttle. If you touch this load path, re-measure with `scripts/validate-corpus-ui.mjs` (13 browser checks; needs `npm i --no-save playwright`) before assuming it's still fine.
- `poolFor(genderFilter)` picks which shuffled array is active; the deck for whoever's currently swiping is `pool.filter(name not already in their picks)`.

## Screens / flow

1. **Loading** — brief centered text while `useStore()` reads localStorage.
2. **Welcome** (only when `!state.onboarded`) — full-page, replaces all chrome. Collects your name (required), partner's name (optional), last name (optional), and a girl/boy/both selector, then persists and drops straight into the swipe screen. No separate "confirm" step.
3. **Swipe** (default view) — the main screen. Layout top to bottom:
   - Header row: a **segmented control** (one pill, two tappable halves, a sliding dark "thumb" behind whichever swiper is active) on the left for choosing who's swiping; "MATCHES · N" chip and a flat outlined gear icon on the right, vertically aligned to the bottom of the segmented control.
   - Card stack (flex, fills remaining vertical space) — a "Hello My Name Is" sticker: colored band up top (pink for girl names, blue for boy names, chosen per-card via `item.g`; a neutral slate tone instead whenever the swiper's `genderFilter` is "both", regardless of the individual card's gender) with "HELLO / MY NAME IS", then a ruled cream writing area showing the name in cursive, with the last name (if set) smaller and muted gray directly beneath it. No shadow, no per-depth lift/scale animation, no card-number counter — these were all removed deliberately (see "Design decisions" below). Swiping drags/rotates only the top card; cards behind it are visually identical and don't move when the stack advances.
   - Controls row: ✕ (pass) / ↺ (undo, disabled when no history) / ♥ (keep) — plain circular buttons, unchanged since the original prototype.
4. **Matches** (toggled via the "MATCHES · N" chip) — full list of names both swipers kept ("Both said yes"), then the current swiper's own keeps, then Copy Backup / Restore (JSON via clipboard or a prompt fallback) and a destructive "START [NAME] OVER" button that clears just that swiper's picks.
5. **Settings** (toggled via the gear icon) — **fully replaces the screen**, no header/chrome carried over, since it's a distinct context, not swipe-adjacent. Same four fields as Welcome, pre-filled, **auto-saving** on a ~400ms debounce as you type/toggle (no explicit Save — this was a deliberate simplification over an earlier Cancel/Save version). Below the fields: a "RESET EVERYTHING ON THIS DEVICE" danger button (confirm dialog → wipes to a fresh `onboarded: false` state, dropping back to Welcome), then an "About" section (portfolio link, GitHub source link, "Build [short commit sha]"), then a single "BACK" button pinned to the bottom.

## Other standing features

- **Update-available toast**: `useUpdateCheck()` polls `/version.json` (written by CI with the deploying commit's SHA) against `import.meta.env.VITE_COMMIT_SHA` baked into the running bundle, on an interval and on tab refocus. On mismatch it shows a small pill near the top: "New version available — install now?" with an INSTALL button that just does `location.reload()`. There's no service worker in this app (unlike `contraction-timer`) — this polling is the only update mechanism, and a user must force-quit/reopen or tap Install to actually get new code, since the page can sit open indefinitely otherwise.
- **Mobile viewport hardening**: `100dvh` (not `100vh`) + `overflow: hidden` + `overscroll-behavior: none` on both the app root and `html`/`body`, plus `env(safe-area-inset-*)` padding throughout — this stack was built up over several rounds of fixing real iOS Safari bugs (rubber-band scroll, notch/home-indicator overlap, horizontal pan from a WebKit flexbox `min-width: auto` bug). Any new full-bleed layout work should keep `minWidth: 0` on flex children to avoid reintroducing that horizontal-scroll bug.
- **iOS input zoom**: all text inputs are pinned to `fontSize: 16` — WebKit auto-zooms the page on focus for any input under 16px and doesn't reliably zoom back out. Don't drop this below 16.
- **No card shadow, on purpose**: box-shadow was tried multiple ways (depth-based, then flattened, then split across separate transform/shadow/overflow-clip layers to dodge known WebKit compositing bugs) and real iOS Safari kept rendering it inconsistently in ways neither Chromium nor even a real WebKit build on Linux (see below) reproduced. It was removed entirely rather than keep chasing engine-specific rendering. If shadow ever comes back, test it on an actual iOS device before trusting any local render.
- **WebKit testing locally**: Playwright's WebKit browser can run on this Linux box for cross-engine checks the default Chromium-based testing misses (`npm install playwright`, `npx playwright install webkit`, `sudo npx playwright install-deps webkit` for the GTK/GStreamer system libs it needs). It's WebKitGTK, not Apple's actual engine, so treat a clean render there as strong evidence, not proof, for iOS-only bugs.

## Design decisions worth preserving

- Everything is intentionally low-key/muted (dusty pink/blue, terracotta accents) — a bright/saturated palette was explicitly rejected twice (red card band called "sickly," a slate/gray option called "millennial gray").
- Motion is minimized on purpose ("people are gonna fire through these quickly") — no lift/scale animation on the card stack, no shadow-driven "pop" when a card advances, no per-card counter to distract from the swipe itself.
- The segmented control (not two separate toggle buttons) was a specific, considered choice to visually merge "who's swiping" into one component, freeing up header space for Matches/Settings.
- Settings is deliberately a separate full-screen context (not layered over swipe chrome) with auto-save instead of Cancel/Save, on the reasoning that a settings screen shouldn't need an explicit commit step for simple profile edits.
