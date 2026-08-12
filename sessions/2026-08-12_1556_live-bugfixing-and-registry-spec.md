# Live Bug-Fixing on Staging, Cost Check, and Spec'ing the ghcr.io Migration

**Date:** 2026-08-12, continuing from the overnight session (2026-08-11)
**Branch:** `backend-accounts-sync`
**Status:** Staging is live and working end to end for a real signed-in user.
Four real bugs found via live device testing were fixed and pushed. Real SMTP
provider decided (Resend, not yet executed). New spec 004 created for a
registry cost cleanup, deliberately not switched to.

## Context

Direct continuation of the overnight autonomous session
(`2026-08-11_0530_implement-and-deploy-backend-accounts-sync.md`), which
implemented and deployed spec 002 end to end. This session picked up once the
user woke up and started actually using the deployed staging site on a real
device — which is exactly the kind of testing that finds bugs automated
end-to-end tests miss, and it found four.

## What happened, roughly in order

1. **Pushed `backend-accounts-sync` to origin** at the user's request —
   staging auto-deploys from any non-`main` branch push, prod only from
   `main`, so this was safe to do without touching prod.

2. **Bug: sign-in redirected to a dead `localhost:3000`.** The Supabase
   project's `site_url` and `uri_allow_list` were still the framework
   defaults from project creation — never configured for the actual deployed
   origins. Fixed live via the Supabase Management API
   (`PATCH /config/auth`), documented in `api/DEPLOY.md` as a prerequisite
   step future deploys need to remember.

3. **Bug: `over_email_send_rate_limit`.** Supabase's built-in auth email
   sender caps at 2/hour, and testing (mine and the user's) had already used
   up the window — confirmed directly via the auth API's error response, not
   guessed. This is the known limitation from `docs/remaining-items.md` §1,
   not a new bug. Led to a real SMTP provider discussion — see below.

4. **Bug: staging sign-ins landed on the prod app.** The allow-list fix in
   step 2 only listed the `/**` wildcard form of each origin
   (`https://.../**`); Supabase's glob matching doesn't treat that as
   covering the bare origin with nothing after it, which is exactly what
   `emailRedirectTo: window.location.origin` sends. It silently fell back to
   `site_url` (set to prod) regardless of which site initiated sign-in.
   Fixed by listing both the bare origin and the wildcard form for every
   site. Documented in `DEPLOY.md` as the sharper version of the same trap.

5. **Bug: permanently stuck on "Loading…" after a real magic-link
   sign-in.** The hydration effect's `finally` block only cleared the
   `hydrating` flag when its own async instance wasn't `cancelled`.
   `hydratedRef.current` already guarantees the hydration fetch itself only
   ever starts once per sign-in — but Supabase's magic-link/PKCE exchange
   fires the auth-change callback more than once in quick succession as the
   session gets established, which re-ran the effect and marked the instance
   actually holding the in-flight fetch as `cancelled` by the time it
   resolved. Every test in the overnight session injected a pre-formed
   session directly into `localStorage`, which only fires the callback once
   — nothing exercised a real magic-link exchange until the user did.
   Fixed: clearing `hydrating` is now unconditional. Commit `56d77b3`.

6. **Bug: "boomerang" swiping — a decided name reappearing at the top of the
   deck.** Reported with a screen recording; confirmed visually (Jailyn
   swiped away, Audrey shown, Jailyn back a few swipes later). Root cause:
   `stateRef` — the "read the true latest state right now" ref that
   `decide`/`undo`/`fetchMore` all depend on — was synced via a `useEffect`
   keyed on `[state]`. Passive effects run after paint, not synchronously
   with the `setState` that triggered them, so a fast-follow swipe could read
   a stale ref and reprocess an already-decided card. Fixed by moving the
   ref sync into `useStore`'s `persist`/`reload`/initial-load calls directly,
   so every consumer sees the true latest state with no effect-timing gap at
   all. Verified with a stress test: 15 swipes at a realistic-fast cadence
   (just past the existing 260ms fly-animation cooldown) against a live
   account — correct order, no duplicates, no skips, no reappearances.
   Commit `26cdafb`.

   Honest caveat recorded for the user at the time: I could reproduce and
   fix the *mechanism*, but couldn't get the exact video sequence to
   reproduce via simulated clicks (touch drags on a real device behave
   differently than synthetic click events). Flagged the ↺ undo button —
   positioned between ✕ and ♥ — as a plausible alternate/contributing
   explanation worth ruling out if it recurs, since it's easy to fat-finger
   during fast swiping and undo is *supposed* to put the last card back.

7. **Real SMTP decision: Resend.** Researched Resend vs. Brevo vs. Mailgun
   free tiers, initially recommended Resend on fit/simplicity grounds. The
   user reframed the question around the app's stated future — eventual
   distribution and a paid tier, with marketing email "not that far off" —
   which raised whether picking narrowly for today's job risked a second
   migration later. Checked and confirmed Resend shipped Audiences and
   Broadcasts (contacts, segments, a campaign builder, open/click tracking)
   as first-party features in 2024, meaning it can plausibly carry both jobs
   — transactional auth email now, marketing campaigns later — under one
   account. That firmed up the recommendation rather than changing it.
   Decision and full comparison recorded in `docs/remaining-items.md` §1.
   **Not yet executed** — the user needs to sign up (their identity/billing,
   not something to automate on their behalf), get DNS records, and hand off
   SMTP credentials. DNS for `calebdudley.dev` is Terraform-managed in the
   sibling `caleb-dudley-dev` repo, already confirmed accessible locally for
   when that step happens.

8. **Cost check-in.** Queried Azure Cost Management directly (not estimated)
   for `baby-names-rg`, current billing period: Container Apps (the app, the
   keepalive job, the Consumption environment) — **$0.00**. Container
   Registry — **$0.08** (the Basic-tier flat fee, prorated for about a day).
   Log Analytics and both Static Web Apps — **$0.00**. Total **~$0.08**,
   entirely the one line item ACR was always known to cost (see the
   overnight session's deploy notes). Confirms the Consumption/`minReplicas:
   0` design is holding up under real usage, not just idle.

9. **ghcr.io discussion → spec 004.** The user asked why not use GitHub
   Container Registry instead of ACR, given they don't mind the image being
   public. Checked rather than assumed: the `baby-names` repo is already
   public (so a public image adds no real exposure), and the existing
   `GITHUB_PAT` is a fine-grained token whose package-push permission wasn't
   yet confirmed. Laid out the real trade-off (eliminates the only paid line
   item; costs one extra manual command since ghcr has no `az acr build`
   equivalent) rather than just switching. The user asked to formalize it as
   its own spec via `/speckit-specify`, explicitly **not** switching the
   active branch/context to it. Created `specs/004-ghcr-registry-migration/`
   (spec.md + a passing requirements checklist) and left
   `.specify/feature.json` pointing at `002-backend-accounts-sync`, since no
   `before_specify` git hook is configured in this repo to auto-branch
   anyway. Two user stories: P1 migrate to ghcr.io (drop-in, no user-facing
   change), P2 decommission the now-unused ACR instance as its own
   explicitly-confirmed deletion, kept separate from P1 on purpose since it's
   destructive. Not planned or implemented — spec only, per the request.

## Commits this session (on `backend-accounts-sync`, all pushed)

```
815dbab Specify moving the API's container registry to ghcr.io (spec 004)
26cdafb Fix swiped names reappearing at the top of the deck (boomerang)
517b55c Record the Resend decision for real SMTP in remaining-items.md
56d77b3 Fix permanent Loading-screen hang on a real magic-link sign-in
0c63ec4 Fix Supabase redirect allow-list: bare origin, not just wildcard
a7f0b6d Document the Supabase redirect-URL trap in DEPLOY.md
903565e Fix Backspace swallowed on the SignIn email field (regression of #1)
```

(`a7f0b6d` is step 2's fix — `site_url`/`uri_allow_list` applied live via the
Supabase Management API, documented after the fact.)

## State at end of session

- Staging (`baby-names.test.calebdudley.dev`) is live, on the latest commit,
  and has been confirmed working through a real sign-in by the user (after
  the fixes above landed).
- Prod is untouched — nothing has merged to `main`.
- Real Azure spend to date: ~$0.08, all Container Registry, exactly as
  expected.
- `backend-accounts-sync` has 6 new commits since the overnight session's own
  summary was written, all pushed to origin.
- Spec 004 exists but is unplanned and unimplemented, sitting alongside spec
  003 (AI name filter, also unplanned/unimplemented) as queued future work.

## Open items for next time

1. **Resend signup** — waiting on the user; DNS records go into
   `caleb-dudley-dev`'s Terraform once available, then Supabase SMTP config
   + `secrets/.env` + `DEPLOY.md`.
2. **ghcr.io migration (spec 004)** — specified, not planned or built. Needs
   `/speckit-plan` and `/speckit-tasks` (or a direct implementation pass) if
   and when the user wants to proceed, plus confirming the `GITHUB_PAT` can
   actually push packages before committing to the approach.
3. **T089 from spec 002** (keepalive job succeeding on its actual daily
   schedule, not just a manual trigger) was still open as of the overnight
   session's summary — worth a 10-second check
   (`az containerapp job execution list --name baby-names-keepalive
   --resource-group baby-names-rg -o table`) next time this comes up, if not
   already confirmed.
4. **Watch for a recurrence of the boomerang bug** despite the fix — see the
   honest caveat in item 6 above. If it recurs, check whether it correlates
   with the ↺ undo button specifically before assuming the ref-timing fix
   didn't fully address it.

## Key learnings

1. **A real device in the user's hands is still the best fuzzer.** All four
   bugs this session were found by the user actually using the app, not by
   any test I wrote — three of the four (redirect config, the allow-list
   glob-matching gap, and the magic-link double-callback race) specifically
   depend on the real Supabase auth flow end to end, which every automated
   test in the overnight session sidestepped by injecting a session directly
   to save the 2/hour email quota. That trade-off was correct for volume
   testing, but it has a real coverage gap, and the fourth bug (boomerang)
   needed a screen recording to even see clearly, let alone diagnose.
2. **Passive `useEffect` timing is a recurring source of "impossible" bugs
   in this codebase now.** Both the Loading-screen hang and the boomerang
   swipe bug trace back to the same root shape: something read a ref that a
   `useEffect` was supposed to keep in sync, and the effect hadn't run yet.
   Twice in one session is enough to call it a pattern — any future ref that
   needs to be "the true current state, right now" should be written
   synchronously alongside the `setState` call that changes it, not synced
   via a separate effect.
3. **A cost question deserves a real number, not an estimate.** Queried
   Azure Cost Management directly rather than reasoning from the deploy
   config about what costs *should* be — cheap to do, and it's the only way
   to actually confirm a $0-by-design system is behaving that way under real
   traffic, not just idle.
4. **"Don't switch to it" is a real, followable constraint for
   `/speckit-specify`** when there's no `before_specify` git hook configured
   — spec creation and branch creation are separable, and this repo already
   has them separated by default.
