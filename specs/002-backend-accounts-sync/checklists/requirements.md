# Specification Quality Checklist: Backend, Accounts & Sync

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-10
**Feature**: [spec.md](../spec.md)

## Content Quality

- [~] No implementation details (languages, frameworks, APIs) — see note 1
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [~] No implementation details leak into specification — see note 1

## Notes

1. **Deliberate deviation on implementation detail.** The owner specified the
   stack directly in the feature description (Python/FastAPI/Pydantic v2,
   Postgres/SQLAlchemy/Alembic, Azure Container Apps, Supabase, pyright strict,
   pytest-first, `make check` via testcontainers). Rather than launder it into
   vague language and lose it, it is recorded verbatim in a fenced
   **Owner-mandated technical constraints** section as a constraint on planning.
   The Functional Requirements and Success Criteria themselves are kept
   technology-agnostic and testable on their own terms — FR-027 says "a single
   command runs lint, type check, and tests against a disposable database,"
   not "run `make check`." This item is marked `~` rather than failed because
   the leak is contained, labeled, and intentional.

2. **All clarifications resolved 2026-08-10** via `/speckit-clarify`, four
   questions asked and answered:
   - *Account required?* Yes — passwordless email magic link, no guest mode.
     Guest mode lost on cost: a second state model plus a merge path, in the
     exact area (sync) where this feature's risk already sits.
   - *Cost ceiling?* $0, free tiers only, hard stop. Cold starts are handled by
     warming the service and database on app load rather than by paying for
     always-warm hosting.
   - *Deck order?* Per-account deterministic shuffle; the global seed retires.
     Reproducibility was the property worth keeping, not universality.
   - *Rate limiting?* Per-account request cap, generous, soft-failing. Per-IP
     limiting deferred.

3. **Constitution III conflict — resolved 2026-08-10.** Hand-deploying the
   backend contradicts Pipeline-Only Deployments as written. The owner granted
   a **time-boxed deviation** rather than amending the principle: automating a
   deploy path before walking it once by hand would mean writing a pipeline
   against an unknown target. Scope is backend-only (the frontend stays
   pipeline-only), the expiry is the next spec, and four compensating controls
   are named. Recorded in the spec's "Accepted deviation" section; carry it
   into the plan's Complexity Tracking verbatim at `/speckit-plan`.

4. **Pre-release, confirmed 2026-08-10.** The app has no production data, so
   the data-migration user story and its requirement were removed outright
   rather than softened — no import path, no legacy save shapes, and the
   offline cache's value shape is free to change. `babyname-swipe-v3` still
   MUST NOT be renamed. This removed the highest-risk slice of the feature,
   dropping it from 6 user stories to 5. (Clarification then grew the spec back
   to 32 FRs and 12 SCs — warm-up, rate limiting, and per-account ordering.)

5. **2026-08-10: Renumbering.** This spec took the 002 slot; the AI criteria
   filter moved to [003-ai-name-filter](../../003-ai-name-filter/spec.md).
   Cross-references in 001, 003, and `CLAUDE.md` were updated. 003's
   served-order requirements (its FR-004/FR-005) are now satisfied by this
   spec's FR-013/FR-014 and should be re-read as inherited rather than new when
   003 reaches planning. Note that FR-014 now gives each account its own deck
   order, which is what makes 003's "rebuild the deck beyond the furthest
   swiper" possible without affecting other accounts.

6. **2026-08-10: Planned.** `/speckit-plan` produced plan.md, research.md,
   data-model.md, contracts/http-api.md, and quickstart.md. The Constitution
   gate passed with one justified violation (Principle III, the granted
   deviation, recorded in Complexity Tracking) and one **finding against the
   constitution itself**: its "name pool invariants" constraint still requires
   the no-D / no-"ey" letter rules that spec 001 retired, and the fixed-seed
   global deck ordering that this spec's FR-014 retires. Two of that bullet's
   four clauses are stale. Recommended as a separate PATCH-level
   `/speckit-constitution` update, not folded into this feature's branch.

7. **Research changed the plan in three places**, all resolved with the owner
   on 2026-08-10:
   - *The free database deletes itself if left alone.* Pauses after 7 days,
     manual restore, eventual permanent deletion. Mitigated by a **daily
     scheduled Container Apps job** pinging the database directly — same free
     grant (~75 of 180,000 vCPU-seconds/month), no dependency on GitHub, and
     not routed through the HTTP app so an application bug cannot cause data
     loss. Daily rather than weekly, because a 7-day cadence has no margin for
     one failed run.
   - *Built-in auth email only reaches project-team addresses*, 2/hour. Shipping
     on it anyway; the limit is recorded as a spec assumption and the SMTP work
     is deferred to `docs/remaining-items.md`. Consequence: nobody outside the
     project team can sign in this release, and tests must never touch real
     email.
   - *The deck algorithm underflows*, making ~71% of the core sort by strict
     rank past card ~2,118. The port reproduces it faithfully; the bug is
     written up with a reproduction script in `docs/remaining-items.md` as a
     product question rather than a patch.

8. **Scope is a re-platforming, not a capability.** The bar for "done" is that
   a couple notices nothing except signing in. With the migration slice gone,
   feature parity (FR-008) and sync correctness (FR-020, FR-023) now carry the
   risk; partner linking, CI/CD, and criteria filtering are explicitly
   deferred.
