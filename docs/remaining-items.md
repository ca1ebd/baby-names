# Remaining Items

Known work that has been deliberately deferred, with enough detail to pick up
cold. This is not a wishlist — everything here is a decision already made to
ship without something, recorded so it does not get forgotten or rediscovered
the hard way.

**Last updated**: 2026-08-11

---

## 1. Replace the built-in auth email sender with real SMTP

**Deferred from**: spec 002 (backend, accounts & sync)
**Status**: decided (2026-08-11) — provider is **Resend**, not yet executed
**Blocks**: anyone outside the project team using the app at all
**Effort**: small — an afternoon, mostly account setup and DNS propagation time

### What we shipped instead

Spec 002 uses passwordless magic-link sign-in via Supabase's **built-in** auth
email service. That service has two limits that matter:

- **It only delivers to addresses on the Supabase project's team.** An email to
  anyone else is refused outright. It is a testing facility, not a sender.
- **2 emails per hour**, across all auth flows combined — identical on Supabase's
  Free and Pro ($25/mo) plans; upgrading Supabase does not raise this. This was
  hit for real during the deploy validation session (2026-08-11): a second
  magic-link send within the hour came back `over_email_send_rate_limit`.

### What this means today

The app is usable by the owner and by anyone explicitly added as a member of
the Supabase project. Nobody else can sign in — not "sign-in is slow for them,"
but *no magic link is ever delivered*.

Two practical consequences while this stands:

- **The partner's email address must be added to the Supabase project team**
  before they can sign in. If sign-in "doesn't work" for them, check this first.
- **The 2/hour cap will bite during development.** Manually testing the sign-in
  flow more than twice in an hour locks you out. Automated tests must not go
  through real email at all — backend tests mint JWTs directly, and local work
  should use the Supabase CLI's local mail catcher.

### The decision: Resend, over Brevo and Mailgun

Compared on 2026-08-11 given the owner's stated plan to eventually distribute
this app and sell a paid tier — cost of switching later turned out to be the
wrong axis to optimize (the Supabase side of an SMTP swap is just host/port/
user/pass in a dashboard, essentially free to redo), so the deciding factor
was which provider needs revisiting the least as the app grows:

| | Resend | Brevo | Mailgun |
|---|---|---|---|
| Free tier | 3,000/month | 300/day (~9,000/mo) | 100/day (~3,000/mo) |
| Card required | No | No | No |
| Built for | Transactional specifically | Full marketing suite | Transactional + parsing/routing |
| Marketing email path later | **Built in** — Audiences + Broadcasts shipped 2024 (contacts, segments, campaign builder, open/click tracking) | Already there, but you're inside a marketing platform to send one magic link today | None — would need a second provider when marketing email happens |

Resend's free tier is absurd overkill for two users' occasional sign-ins, but
the deciding point was the Audiences/Broadcasts features: they mean Resend can
plausibly carry both jobs — transactional auth email now, marketing campaigns
later — under one account, rather than running two providers or migrating
everything once marketing email becomes real. Brevo's free tier is
technically the most generous, but it's marketing-platform weight for a
one-email job today. Mailgun has no marketing story and free-tier terms that
have shifted more than once historically.

### What the work is

1. **Owner signs up** for Resend (resend.com, free, no card) — not something to
   automate on the owner's behalf, since it's tied to their identity/billing.
2. **Add a sending subdomain**, not the bare domain — e.g. `mail.calebdudley.dev`
   — so transactional mail reputation is cleanly scoped and can't affect the
   main domain. Resend returns SPF/DKIM (and a recommended DMARC) records to add.
3. **Add those DNS records** in `caleb-dudley-dev`'s Terraform (DNS for
   `calebdudley.dev` is centrally managed there, per this repo's `CLAUDE.md`),
   then `terraform apply` and wait for propagation/verification in Resend.
4. **Generate SMTP credentials** in Resend (host/port/user/pass, not just an
   API key — Supabase's custom SMTP wants SMTP, not Resend's HTTP API) and
   configure them in Supabase (Authentication → Emails → SMTP Settings, or via
   the Management API's `PATCH /config/auth`, same pattern already used for
   the `site_url`/`uri_allow_list` fixes in `api/DEPLOY.md`).
5. Store the SMTP credentials in `secrets/.env` (never committed) and document
   the step in `api/DEPLOY.md`, next to the existing Supabase auth-config traps
   it already records.
6. Once live, delete the "authorized addresses only" caveat from spec 002's
   assumptions — anyone can sign in at that point, not just the project team.

### Why it was deferred

The app had no users beyond the owner when spec 002 shipped. Standing up a
fourth external service to serve two people whose addresses can simply be
added to the project team was work with no payoff yet. It became a live
problem the same day, once real end-to-end testing exercised the 2/hour cap —
see `sessions/2026-08-11_0530_implement-and-deploy-backend-accounts-sync.md`
and the same day's follow-up conversation for how it was found.

---

## 2. The deck algorithm silently stops shuffling past ~card 2,118

**Deferred from**: spec 002 (found during planning; the behavior originates in
spec 001's frontend implementation)
**Blocks**: nothing. Affects deck quality deep into a long session.
**Effort**: small to change, but it is a **product** decision first

### The bug

`weightedShuffle` in `src/BabyNameSwipe.tsx` gives each name a sort key of
`u^(rank+1)`, where `u` is a seeded uniform random draw. The intent, documented
in the code and in `CLAUDE.md`, is that a name's chance of surfacing early
falls off with its popularity rank while nothing is excluded.

That intent holds for the first couple of thousand cards and then quietly stops
holding, because the key underflows.

`u^(rank+1)` drops below float64's smallest representable value long before the
end of the core. For a typical `u ≈ 0.5` that happens around rank 1,075.
Measured against the real girl core (7,457 names, seed `20260730`):

| Measurement | Value |
|---|---|
| Keys that underflow to exactly `0.0` | **5,339 of 7,457 (71.6%)** |
| First rank to underflow | **230** |
| Dealt position after which order is strict rank | **~2,118** |

Every underflowed name has the identical key `0.0`. `Array.prototype.sort` is
stable, so all of them keep their original relative order — which is rank order.
The real behavior is therefore:

1. Roughly the first ~2,100 dealt cards are genuinely popularity-weighted.
2. **Everything after that is strict rank order, not a shuffle.**
3. Then the flat-shuffled tail, which is unaffected.

Reproduce it with:

```bash
node -e "
function rng(s){s=s>>>0;return()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};}
const next=rng(20260730), keys=[];
for(let i=0;i<7457;i++) keys.push(Math.pow(next(), i+1));
console.log('zeros:', keys.filter(k=>k===0).length, 'first at rank:', keys.findIndex(k=>k===0));
const order = keys.map((k,i)=>({k,i})).sort((a,b)=>b.k-a.k).map(e=>e.i);
console.log('dealt positions 3000-3005 are ranks:', order.slice(3000,3006).join(','));
"
```

### Why it was not fixed

Spec 002 moves deck generation to the backend, and its entire premise is that a
couple notices nothing except signing in. The port therefore **reproduces this
behavior exactly**, including the underflow, with an explicit `(key DESC, rank
ASC)` tie-break so the stability JavaScript provided implicitly survives the
move to Python.

Fixing it during a re-platforming would have changed what users see past card
~2,100 while every parity test still passed — spec 002's SC-003 only exercises
500 names, so nothing would have caught it. That is the worst way to ship a
behavior change.

### What the work is

The mechanical fix is one line: sort by `(rank + 1) * ln(u)` descending, which
is mathematically identical and numerically stable, so no key underflows and
the weighting holds across the whole core.

**The question to answer first is whether that is actually better.** Strict
rank order deep in the deck is not obviously wrong — a user 2,000 names in has
exhausted the popular names, and walking the remainder in popularity order may
read as more sensible than a shuffle. Nobody has ever seen the alternative, so
this needs judgment, not just a patch.

If it is changed, note that it changes the deck for existing accounts from card
~2,100 onward. Since served order is frozen up to the furthest swiper's
position (spec 002's FR-013), history is safe either way — only undealt names
would reorder.

---

## 3. No frontend test framework — client-side FRs shipped without a failing-first test

**Deferred from**: spec 002 (backend, accounts & sync)
**Blocks**: nothing functionally. Weakens FR-028's test-first guarantee for
everything in `src/`
**Effort**: medium — picking and wiring a framework is the real cost, not the
tests themselves

### What we shipped instead

Spec 002's FR-028 requires every behavioral change to originate as a test that
fails before the implementation exists, and `make check` is the single gate
that's supposed to prove it. That held throughout for the backend. It did not
hold for the client: this repo has no frontend test framework at all (no
Vitest, no Jest, no component-level Playwright) — `make check-web` is lint +
`tsc` + a production build, none of which can fail on a behavioral regression.

A full FR-to-test trace (T079) found every client-side requirement from spec
002 shipped without a test that could have failed first: FR-006 (sign-out
clears the cache), FR-018 (offline swipe/undo/Matches), FR-019/FR-021/FR-022
(the outbox, low-water-mark refill, and offline-exhaustion messaging), plus
the account/session requirements FR-001, FR-003, FR-008, FR-010, FR-011. The
backend-side E2E validation done during that implementation session (real
Supabase session, real deployed Container App, Playwright driving a built
bundle) caught three real bugs none of `make check`'s tests could have — but
that was a one-off manual pass, not something `make check` runs or can rerun.

### Why it was not fixed

Bootstrapping a frontend test framework mid-feature is a bigger call than one
pass through an existing task list should make unilaterally — it's a standing
decision about how this codebase tests itself going forward, not a bug fix.
`src/BabyNameSwipe.tsx` also carries `// @ts-nocheck` on purpose (see
`CLAUDE.md`) as a low-formality holdover from its prototype origins; adding
real tests on top of it is worth doing deliberately, not as a 3am add-on.

### What the work is

1. Pick a framework — Vitest is the natural fit given Vite is already the
   build tool; Playwright component/E2E tests are the natural fit for
   anything that needs a real browser (drag gestures, `localStorage`).
2. Wire it into `make check-web` so a broken client behavior actually fails
   the gate, the same way pytest does for the backend.
3. Write the tests FR-028 already required for FR-001/003/006/008/010/011/
   018/019/021/022 — each is a specific, already-known behavior, not
   exploratory work.

---

## Also outstanding

Smaller items recorded elsewhere, collected here so there is one place to look.

- **Account deletion and data export** — not specified in spec 002. Flagged as
  the one Outstanding category in that spec's clarification coverage. Low impact
  at two users; worth settling before any public launch.
- **Backend CI/CD** — deliberately the next spec. Spec 002 deploys by hand
  under a time-boxed deviation from the constitution's pipeline-only principle,
  which expires when that spec ships.
