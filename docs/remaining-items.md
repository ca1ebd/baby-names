# Remaining Items

Known work that has been deliberately deferred, with enough detail to pick up
cold. This is not a wishlist — everything here is a decision already made to
ship without something, recorded so it does not get forgotten or rediscovered
the hard way.

**Last updated**: 2026-08-10

---

## 1. Replace the built-in auth email sender with real SMTP

**Deferred from**: spec 002 (backend, accounts & sync)
**Blocks**: anyone outside the project team using the app at all
**Effort**: small — an afternoon, mostly account setup

### What we shipped instead

Spec 002 uses passwordless magic-link sign-in via Supabase's **built-in** auth
email service. That service has two limits that matter:

- **It only delivers to addresses on the Supabase project's team.** An email to
  anyone else is refused outright. It is a testing facility, not a sender.
- **2 emails per hour**, across all auth flows combined.

### What this means today

The app is usable by the owner and by anyone explicitly added as a member of
the Supabase project. Nobody else can sign in — not "sign-in is slow for them,"
but *no magic link is ever delivered*. That is acceptable while the app is
pre-release with two known users, and it is the reason this is deferred rather
than a bug.

Two practical consequences while this stands:

- **The partner's email address must be added to the Supabase project team**
  before they can sign in. If sign-in "doesn't work" for them, check this first.
- **The 2/hour cap will bite during development.** Manually testing the sign-in
  flow more than twice in an hour locks you out. Automated tests must not go
  through real email at all — backend tests mint JWTs directly, and local work
  should use the Supabase CLI's local mail catcher.

### What the work is

1. Sign up for a free-tier transactional email provider. Resend, Brevo, and
   Mailgun all have free allowances orders of magnitude beyond what this app
   needs. Any of them satisfies the $0 cap in spec 002's FR-024.
2. Configure it as custom SMTP in the Supabase dashboard (Authentication →
   Emails → SMTP Settings). Supabase's own auth rate limit then rises to ~30
   new users/hour, which is irrelevant at this scale.
3. Verify the sending domain (SPF/DKIM) or magic links land in spam, which
   presents to a user as the same thing as not working.
4. Update `api/DEPLOY.md` with the SMTP credentials step, and delete the
   "authorized addresses only" caveat from spec 002's assumptions.

### Why it was deferred

The app has no users beyond the owner. Standing up a fourth external service to
serve two people whose addresses can simply be added to the project team is
work with no payoff yet. It becomes mandatory the moment anyone else needs an
account.

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

## Also outstanding

Smaller items recorded elsewhere, collected here so there is one place to look.

- **Account deletion and data export** — not specified in spec 002. Flagged as
  the one Outstanding category in that spec's clarification coverage. Low impact
  at two users; worth settling before any public launch.
- **The constitution's name-pool invariants are stale** — `.specify/memory/
  constitution.md` still requires the no-"D" / no-"ey" letter rules that spec
  001 retired, and the global fixed-seed deck ordering that spec 002's FR-014
  retires. Two of that bullet's four clauses no longer describe the project.
  Wants a PATCH-level `/speckit-constitution` amendment.
- **Backend CI/CD** — deliberately the next spec. Spec 002 deploys by hand
  under a time-boxed deviation from the constitution's pipeline-only principle,
  which expires when that spec ships.
