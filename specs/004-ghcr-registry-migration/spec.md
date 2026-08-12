# Feature Specification: Move the API's container registry to ghcr.io

**Feature Branch**: `004-ghcr-registry-migration`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "Move the backend API's container image off Azure
Container Registry (ACR) and onto GitHub Container Registry (ghcr.io),
published as a public image. The baby-names GitHub repository is already
public, so a public image built from that same source adds no meaningful
exposure. The current setup (from spec 002's deploy) uses `az acr build`
against `babynamesacr` (an Azure Container Registry, Basic SKU) which costs a
small flat recurring fee (~$5/month, prorated) — the only nonzero recurring
line item in the whole Azure spend for this project, everything else
(Container Apps Consumption, the keepalive job, Log Analytics, Static Web
Apps Free tier) is genuinely $0. Switching to a public ghcr.io image
eliminates that cost entirely and also simplifies the Azure Container App's
pull configuration, since a public image needs no registry credentials/secrets
at all (currently the Container App holds an ACR registry secret for
pulling). The new deploy path builds and pushes the image locally via
`docker build`/`docker push` rather than the cloud-side `az acr build`,
authenticated against ghcr.io with a GitHub token that has package-write
permission. Scope includes: verifying/obtaining a token with the right
permission, building and pushing the image to ghcr.io under the repo owner's
namespace, redeploying the Container App (and the keepalive Container Apps
Job, which shares the same image) to pull from ghcr.io instead of ACR,
updating api/DEPLOY.md's build-and-push and redeploy sections end to end
(including the existing digest-pinning-and-force-new-revision gotcha, which
still applies regardless of registry), and — as a separate, explicitly
confirmed step since it's a delete — decommissioning the now-unused
babynamesacr Azure Container Registry instance. Out of scope: any GitHub
Actions CI/CD automation of the build/push step — this stays a manual runbook
step."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deploy from a free public registry (Priority: P1)

The operator builds the backend's container image and pushes it to a public
GitHub Container Registry (ghcr.io) repository instead of the paid Azure
Container Registry instance. The running service — both the API and the daily
keepalive job — pulls that image with no registry credentials at all, since
it's public. The deploy runbook documents the new steps end to end.

**Why this priority**: This is the entire point of the feature — it removes
the only nonzero recurring cost in the deployment and simplifies the running
config (no pull secret to manage) — and it is a drop-in infrastructure swap
with no change to what the service does, so it is safe to do first and
independently of the cleanup in User Story 2.

**Independent Test**: Follow the updated runbook to build, push, and redeploy
from ghcr.io on a service that's currently running from ACR. Confirm the
service is reachable and behaves identically (health check, sign-in, deck
fetch, sync all still work) with the ACR-hosted image no longer in use.

**Acceptance Scenarios**:

1. **Given** a built container image, **When** it is pushed to ghcr.io under
   the repository owner's namespace, **Then** it is publicly pullable with no
   authentication.
2. **Given** the Container App and the keepalive Container Apps Job
   redeployed against the ghcr.io image, **When** either runs, **Then** it
   starts successfully with no registry credential configured.
3. **Given** the runbook's new build-and-push section, **When** followed step
   by step by someone who has not done it before, **Then** it produces a
   working, reachable service.

---

### User Story 2 - Retire the registry that's no longer earning its cost (Priority: P2)

Once the ghcr.io-based deploy is confirmed working, the operator deletes the
now-unused Azure Container Registry instance, so its recurring charge
actually stops rather than merely becoming redundant.

**Why this priority**: Separable from User Story 1 on purpose — it's a
destructive action (deleting a resource) and the savings from User Story 1
alone are marginal until the old registry is actually removed, so this is
gated as its own explicitly confirmed step rather than folded into the
migration itself.

**Independent Test**: Confirm the Azure Container Registry resource no longer
exists in the resource group, and that the next cost check shows no Container
Registry line item at all.

**Acceptance Scenarios**:

1. **Given** the service has been running successfully from ghcr.io for a
   period the operator is comfortable with, **When** the operator explicitly
   confirms the deletion, **Then** the Azure Container Registry instance is
   removed.
2. **Given** the registry has been removed, **When** the resource group's
   cost is checked, **Then** no Container Registry cost appears in any
   subsequent billing period.

---

### Edge Cases

- **The push credential lacks package-write permission**: the existing
  GitHub token may or may not already grant it; verifying this — and
  obtaining a token that does, if not — is part of User Story 1, not a
  precondition decided in advance.
- **A rollback to a previous image is needed**: ghcr.io must retain more than
  just a `latest` tag reachable by digest, the same way the ACR-hosted image
  did, so a previous version can still be pinned to by digest if a redeploy
  needs to be reverted.
- **The GitHub repository's visibility changes later**: ghcr.io package
  visibility is independent of repository visibility — if `baby-names` were
  ever made private, the image's public/private status would need a
  deliberate, separate decision at that time, not an automatic one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The backend API's container image MUST be hosted on GitHub
  Container Registry (ghcr.io) rather than Azure Container Registry.
- **FR-002**: The container image MUST be publicly readable, so that the
  Azure Container App and Container Apps Job can pull it with no registry
  credential configured.
- **FR-003**: The deploy runbook MUST document the exact local build-and-push
  steps that replace `az acr build`, including how to obtain and use a
  GitHub credential with permission to push to ghcr.io.
- **FR-004**: The redeployed Container App and the keepalive Container Apps
  Job MUST both reference the ghcr.io image, and the existing practice of
  pinning to an explicit digest and forcing a new revision on every redeploy
  (documented in `api/DEPLOY.md`) MUST continue to apply — that behavior is a
  property of Azure Container Apps, not of the registry, and remains a trap
  regardless of where the image is hosted.
- **FR-005**: The Azure Container Registry instance MUST NOT be deleted until
  the ghcr.io-based deploy has been confirmed working end to end, and MUST
  require the operator's explicit confirmation immediately before the
  deletion happens.
- **FR-006**: The repository MUST continue to contain no credentials — the
  ghcr.io push credential is supplied out-of-band and MUST never be
  committed, consistent with the existing requirement that governs every
  other deploy credential in this project.
- **FR-007**: Once the Azure Container Registry instance is decommissioned,
  its recurring cost MUST no longer appear in the resource group's billing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Following the updated runbook from a clean state produces a
  working service pulling its image from ghcr.io, with the Azure Container
  Registry cost no longer accruing.
- **SC-002**: The service's observable behavior — health check, sign-in, deck
  fetch, offline sync — is unchanged before and after the migration; the
  registry switch produces no functional regression.
- **SC-003**: The repository contains no ghcr.io or GitHub push credential at
  any commit.
- **SC-004**: Azure Container Apps' own cost remains $0 after the migration,
  unaffected by the registry change.
- **SC-005**: After the Azure Container Registry instance is decommissioned,
  a resource-group cost check shows no Container Registry line item in the
  following billing period.

## Assumptions

- The `baby-names` GitHub repository remains public for the life of this
  decision; a public container image is judged to add no meaningful exposure
  on that basis. If the repository's visibility ever changes, the image's
  visibility needs its own explicit revisit — the two are not linked
  automatically by GitHub.
- Image tagging stays consistent with current practice (`:latest`, redeployed
  by resolving and pinning to an explicit digest) rather than introducing a
  new tagging scheme such as commit-SHA tags; that is a separate improvement,
  not required by this migration.
- No GitHub Actions automation is introduced for the build/push step — it
  remains a manual command the operator runs, consistent with this project's
  constitution (Pipeline-Only Deployments governs the frontend specifically)
  and with backend CI/CD being deliberately deferred to a later spec.
- Docker is available on the machine performing the deploy (already
  confirmed present on the implementing machine used for spec 002's deploy).
