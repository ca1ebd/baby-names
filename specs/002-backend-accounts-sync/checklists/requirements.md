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

- [ ] No [NEEDS CLARIFICATION] markers remain — 2 open (Q1, Q2)
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

2. **Two open clarifications** (Q1: is an account required, or is there a guest
   mode; Q2: monthly cost ceiling). Both were judged to lack a reasonable
   default: Q1 changes the state model and the permanence of the import path,
   and Q2 is required by Constitution II before any metered service is
   introduced. Resolve via `/speckit-clarify` or answer inline before
   `/speckit-plan`.

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
   MUST NOT be renamed. This removed the highest-risk slice of the feature and
   dropped it from 6 user stories to 5, 30 FRs to 29, and 11 SCs to 10.

5. **2026-08-10: Renumbering.** This spec took the 002 slot; the AI criteria
   filter moved to [003-ai-name-filter](../../003-ai-name-filter/spec.md).
   Cross-references in 001, 003, and `CLAUDE.md` were updated. 003's
   served-order requirements (its FR-004/FR-005) are now satisfied by this
   spec's FR-012 and should be re-read as inherited rather than new when 003
   reaches planning.

6. **Scope is a re-platforming, not a capability.** The bar for "done" is that
   a couple notices nothing except signing in. With the migration slice gone,
   feature parity (FR-007) and sync correctness (FR-019, FR-022) now carry the
   risk; partner linking, CI/CD, and criteria filtering are explicitly
   deferred.
