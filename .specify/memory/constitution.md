<!--
Sync Impact Report
==================
Version change: (template, unversioned) → 1.0.0 → 1.1.0
Rationale: 1.0.0 initial ratification from owner-supplied principles.
           1.1.0 adds Principle V (No AI Vendor Attribution) — MINOR, a new
           principle with no change to existing ones.

Modified principles: n/a (initial adoption)
Added sections:
  - Core Principles (5 principles: Muted Visual Design; Cost Consciousness;
    Pipeline-Only Deployments; Storage Key Stability; No AI Vendor Attribution)
  - Additional Constraints
  - Development Workflow
  - Governance
Removed sections:
  - Fifth principle slot from template (user supplied four principles)

Templates status:
  ✅ .specify/templates/plan-template.md — generic constitution-check gate, compatible
  ✅ .specify/templates/spec-template.md — no constitution references, compatible
  ✅ .specify/templates/tasks-template.md — no constitution references, compatible

Follow-up TODOs: none
-->

# Baby Name Swipe Constitution

## Core Principles

### I. Muted Visual Design

All UI work MUST stay within the app's established low-key, muted palette: dusty
pink/blue with terracotta accents. Bright or saturated color treatments are
prohibited — they have been explicitly rejected in this project's history (a
saturated red card band and a slate/gray "millennial gray" option were both
turned down). Motion MUST remain minimal: no lift/scale card animations, no
shadow-driven "pop", no decorative counters. New features adopt the existing
visual language rather than introducing their own.

**Rationale**: The app is used in quick, repeated bursts ("people are gonna fire
through these quickly"); a calm, muted surface is a deliberate product decision,
not a default to be improved upon.

### II. Cost Consciousness

This project has no revenue, so recurring cost is a first-class design
constraint. Features MUST target free-tier services (the app runs on Azure
Static Web Apps Free tier today) and MUST NOT introduce per-user or per-request
costs without an explicit, user-approved budget. Any feature that consumes a
metered resource (e.g., paid APIs) MUST document its expected cost profile in
its plan, include safeguards against unbounded spend (caps, throttles, or
user-supplied credentials), and prefer the cheapest viable option.

**Rationale**: A hobby app with zero income cannot absorb surprise bills; cost
must be weighed at design time, not discovered on an invoice.

### III. Pipeline-Only Deployments

Production MUST only be deployed through the build pipeline: pushes to `main`
trigger the hand-written GitHub Actions workflow that stamps the commit SHA into
the bundle and deploys to prod. Manual/direct deploys to production (CLI
uploads, portal edits, ad-hoc tooling) are prohibited. Pre-production review
happens on staging, which deploys automatically from non-`main` branches.
Changes to the deploy workflows MUST preserve the commit-SHA stamping that the
update-check feature and About screen depend on.

**Rationale**: The pipeline is what guarantees the deployed bundle, the
`version.json` update check, and the build stamp all agree; bypassing it breaks
the app's only update mechanism and destroys traceability.

### IV. Storage Key Stability

The localStorage key `babyname-swipe-v3` (`STORAGE_KEY`) MUST NOT be changed —
ever — because all user state lives on-device under that single key, and
renaming it would silently orphan every saved swipe. Schema evolution MUST
happen inside the value via backward-compatible migration on load (following
the existing pattern: detect missing fields, backfill defaults, re-persist),
and MUST never force an existing user back through onboarding or discard their
picks.

**Rationale**: There is no backend and no sync; the browser's copy of this key
is the only copy of a couple's swipe history. Losing it is unrecoverable data
loss.

### V. No AI Vendor Attribution

The words "Anthropic" and "Claude", any model name (Opus, Sonnet, Haiku,
Fable, `claude-*`), and any AI-assistant self-attribution MUST NOT appear in
branch names, commit messages or trailers, pull request and issue titles,
bodies or comments, code comments, documentation, release notes, or any other
repository content or metadata. Branches are named after the work
(`expanded-name-corpus`), never after the tool that helped. Where a default or
harness setting would insert such text automatically it MUST be disabled
(`includeCoAuthoredBy: false`); where it cannot be, the contributor MUST say so
explicitly rather than let it through silently.

The only permitted exceptions are functional, not promotional: paths a tool
requires in order to operate (`CLAUDE.md`, `.claude/`, spec-kit's own config
keys). No new exceptions may be added.

**Rationale**: The repository is the owner's work product, not advertising
space for a vendor. Attribution defaults that quietly brand commits and
branches are a marketing artifact, and their removal is not negotiable.

## Additional Constraints

- **Stack**: Vite + React + TypeScript single-page app; UI concentrated in
  `src/BabyNameSwipe.tsx` (deliberately `@ts-nocheck`), styled with inline
  style objects. New code follows these existing conventions.
- **No backend by default**: state persists in localStorage via the
  `window.storage` shim. Introducing any server-side component is a
  constitutional cost question (Principle II) and requires explicit approval.
- **Mobile-first hardening is load-bearing**: `100dvh`, `overflow: hidden`,
  `overscroll-behavior: none`, safe-area insets, `minWidth: 0` on flex
  children, and `fontSize: 16` on inputs exist to fix real iOS Safari bugs and
  MUST be preserved in new layouts.
- **Name pool invariants**: no names starting with "D", none ending in
  "y"/"ie"/"ey", zero overlap between girl and boy pools, and deterministic
  fixed-seed deck ordering across devices.

## Development Workflow

- Feature work happens on non-`main` branches; every push auto-deploys to
  staging (`https://baby-names.test.calebdudley.dev`) for review before
  merging to `main` (prod).
- Features follow the Spec Kit flow: specify → clarify → plan → tasks →
  implement, with the constitution checked at the plan stage's gate.
- Real-device iOS verification is the standard of proof for rendering
  concerns; local WebKitGTK results are strong evidence, not proof.

## Governance

This constitution supersedes ad-hoc practice for all feature work in this
repository. The plan phase of every feature MUST include a constitution
compliance check, and violations MUST be either corrected or explicitly
justified in the plan's complexity/deviation tracking before implementation.

**Amendments**: propose the change in a branch, update this document with a
version bump and Sync Impact Report, and merge through the normal pipeline.
Versioning follows semantic rules — MAJOR for removing/redefining a principle,
MINOR for adding or materially expanding one, PATCH for clarifications.

**Compliance review**: PR review (human or agent) verifies changes against
Principles I–V; anything touching deploy workflows, storage schema, palette,
or metered services gets called out explicitly in the PR description.

**Version**: 1.1.0 | **Ratified**: 2026-08-08 | **Last Amended**: 2026-08-09
