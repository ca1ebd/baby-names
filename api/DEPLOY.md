# Deploy Runbook

Manual deploy for the `api/` service. There is no CI/CD for the backend (that's
deferred to a later spec, see plan.md's Complexity Tracking) — every step here
is a command you run by hand from the implementing machine.

**Before you start**: the `az` CLI is already authenticated on the implementing
machine and `baby-names-rg` (East US 2) already exists — it's the same resource
group hosting the frontend's two Static Web Apps (`baby-names`, `baby-names-test`).
This runbook creates resources *inside* that group; it never creates a new
subscription, login, or resource group. Supabase credentials come from
`secrets/.env` at the repo root (gitignored, never committed) rather than a
freshly created Supabase project — that project already exists and is tied to
the owner's account.

Resource names used throughout, all inside `baby-names-rg` / `eastus2`:

| Resource | Name |
|---|---|
| Container Apps environment | `baby-names-env` |
| Azure Container Registry | `babynamesacr` |
| Container App (the API) | `baby-names-api` |
| Container Apps Job (keepalive) | `baby-names-keepalive` |
| Budget | `baby-names-budget` |

## 0. Prerequisites

- `az` CLI logged in (`az account show` succeeds) with the `containerapp`
  extension installed (`az extension add --name containerapp --upgrade`).
- `secrets/.env` present at the repo root with `DATABASE_URL`,
  `SUPABASE_PROJECT_REF`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `CORS_ORIGINS`,
  `RATE_LIMIT_PER_HOUR`. `DATABASE_URL` must point at Supabase's **transaction
  pooler** (port 6543), not the direct connection — Container Apps' outbound
  networking works better with the pooler, and it's what `data-model.md`
  assumes for concurrent request handling.
- Both users' email addresses added to the Supabase project's team (Auth →
  the project dashboard). Research §4: the built-in auth email sender only
  delivers to project-team addresses. This is what makes sign-in work at all
  for this release — do it before anyone tries to sign in, not after "it
  doesn't work" gets reported.
- **The Supabase project's Site URL and redirect allow-list, or the magic
  link goes nowhere.** A fresh Supabase project defaults `site_url` to
  `http://localhost:3000` with an empty `uri_allow_list` — `signInWithOtp`'s
  `emailRedirectTo` is validated against that list, and a mismatch makes
  Supabase silently fall back to `site_url` instead of erroring. The email
  still sends, the link still "works" in the sense that clicking it does hit
  Supabase's verify endpoint and issue a session — it just redirects the
  browser somewhere other than where the client can consume the session
  token in the URL fragment. This is easy to miss because nothing in the
  deploy path fails loudly; sign-in just doesn't finish, or silently lands
  on the wrong site (prod instead of staging, or vice versa). Fix once per
  project:
  ```bash
  curl -X PATCH "https://api.supabase.com/v1/projects/${SUPABASE_PROJECT_REF}/config/auth" \
    -H "Authorization: Bearer ${SUPABASE_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
      "site_url": "https://baby-names.calebdudley.dev",
      "uri_allow_list": "https://baby-names.calebdudley.dev,https://baby-names.calebdudley.dev/**,https://baby-names.test.calebdudley.dev,https://baby-names.test.calebdudley.dev/**,http://localhost:5173,http://localhost:5173/**"
    }'
  ```
  **List both the bare origin and the `/**` wildcard form of every site.**
  `signInWithEmail` sends `emailRedirectTo: window.location.origin` — no
  trailing slash, no path — and Supabase's allow-list glob matching does not
  treat `https://example.com/**` as matching the bare origin with nothing
  after it. Listing only the wildcard form still falls back to `site_url`
  silently, same as an empty list, just less obviously (the email still
  sends and the link still "half-works"). This bit the initial fix: staging
  sign-ins landed on prod's app instead of staging's, because `site_url` was
  prod and only the wildcard pattern was in the allow list.

  A magic link already clicked against the wrong redirect is spent — the
  server-side verification already happened even though the client couldn't
  complete it. Request a new one after fixing this, not a retry of the same
  link.

## 1. Provision the Container Apps environment

Consumption-only, `minReplicas: 0` on the app later — these two settings are
what keeps this at $0/month (research §1). A Dedicated workload profile or a
nonzero `minReplicas` silently starts a meter.

```bash
az containerapp env create \
  --name baby-names-env \
  --resource-group baby-names-rg \
  --location eastus2
```

This provisions a Consumption environment by default (no `--enable-workload-profiles`
Dedicated profile is added). Confirm:

```bash
az containerapp env show --name baby-names-env --resource-group baby-names-rg \
  --query "properties.workloadProfiles"
```

Should show only the `Consumption` profile.

## 2. Build and push the image

```bash
az acr create --name babynamesacr --resource-group baby-names-rg --sku Basic --admin-enabled true
az acr build --registry babynamesacr --image baby-names-api:latest ./api
```

`az acr build` builds `api/Dockerfile` in the cloud (no local Docker needed)
and pushes straight to the registry.

**Redeploying after a code change does not "just work" from `:latest` alone.**
A Container App revision pins to the image *digest* it resolved at the moment
the revision was created — pushing a new image under the same `:latest` tag
and re-running `containerapp update --image ...:latest` is a no-op, because
the image reference string in the ARM template hasn't changed and Container
Apps only creates a new revision when it has. The old digest keeps serving
traffic, including after a scale-to-zero cold start. This bit the very first
deploy: an auth fix was pushed to `:latest`, `containerapp update` reported
success, and the service kept 401ing on every real Supabase token because it
was still running the pre-fix digest. Always redeploy by resolving the digest
explicitly and forcing a new revision:

```bash
DIGEST=$(az acr repository show --name babynamesacr --image baby-names-api:latest --query "digest" -o tsv)
az containerapp update --name baby-names-api --resource-group baby-names-rg \
  --image "babynamesacr.azurecr.io/baby-names-api@${DIGEST}" \
  --revision-suffix "deploy$(date +%s)"
az containerapp job update --name baby-names-keepalive --resource-group baby-names-rg \
  --image "babynamesacr.azurecr.io/baby-names-api@${DIGEST}"
```

Confirm the new revision is the one actually taking traffic:
`az containerapp revision list --name baby-names-api --resource-group baby-names-rg -o table`.

## 3. Apply migrations

From the repo root, with `secrets/.env` populated:

```bash
make migrate
```

Record the applied revision (`cd api && .venv/bin/alembic current`) — FR-026
wants this traceable. Migrations run from the operator's machine against
Supabase directly; they are not part of the container's startup path.

## 4. Seed the corpus

Immediately after migrations, before anything downstream depends on the names
being there:

```bash
make seed-corpus
```

Idempotent — safe to re-run. Verify row counts match the source (63,880 names;
girl core 7,457, boy core 5,707):

```bash
psql "$DATABASE_URL" -c "select gender, is_core, count(*) from names group by 1,2 order by 1,2;"
```

**This step must happen before `src/lib/nameCorpus.ts` is deleted from the
frontend** (tasks.md T061) — the frontend copy is not what seeds the database;
`api/scripts/seed_corpus.py` reads `api/src/babynames_api/corpus/names.json`,
generated by `scripts/build-name-corpus.mjs --json-out`. If that artifact is
ever missing, regenerate it before seeding.

## 5. Deploy the Container App

Supabase/DB values go in as Container App **secrets**, never plain env vars —
`DATABASE_URL` in particular contains a password.

```bash
az containerapp create \
  --name baby-names-api \
  --resource-group baby-names-rg \
  --environment baby-names-env \
  --image babynamesacr.azurecr.io/baby-names-api:latest \
  --registry-server babynamesacr.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 2 \
  --cpu 0.25 --memory 0.5Gi \
  --secrets \
      database-url="$DATABASE_URL" \
      supabase-project-ref="$SUPABASE_PROJECT_REF" \
      supabase-url="$SUPABASE_URL" \
      cors-origins="$CORS_ORIGINS" \
      rate-limit-per-hour="$RATE_LIMIT_PER_HOUR" \
  --env-vars \
      DATABASE_URL=secretref:database-url \
      SUPABASE_PROJECT_REF=secretref:supabase-project-ref \
      SUPABASE_URL=secretref:supabase-url \
      CORS_ORIGINS=secretref:cors-origins \
      RATE_LIMIT_PER_HOUR=secretref:rate-limit-per-hour
```

`SUPABASE_URL` is easy to miss because `SUPABASE_PROJECT_REF` *looks* like it
should be enough — it isn't. `auth.py`'s JWKS fetch builds its URL from
`settings.supabase_url` directly, not by deriving it from the project ref, so
leaving this one out doesn't fail to deploy or fail the health check; every
authenticated endpoint 500s the moment a real request needs to verify a token
(`httpcore.UnsupportedProtocol: Request URL is missing an 'http://' or
'https://' protocol`, from a JWKS URL that's just `/auth/v1/.well-known/jwks.json`
with an empty scheme+host). Confirm before moving on:

```bash
curl -s "https://$(az containerapp show --name baby-names-api --resource-group baby-names-rg --query "properties.configuration.ingress.fqdn" -o tsv)/v1/state" \
  -H "Authorization: Bearer <any-real-supabase-jwt>"
```

A `401` means JWKS fetching works (the token was rejected on its own merits).
A `500` mentioning `UnsupportedProtocol` means `SUPABASE_URL` didn't make it
into the container's environment.

Note the values are read from the current shell environment — `set -a && .
secrets/.env && set +a` before running this, the same way the Makefile targets
load it.

Confirm `minReplicas` really is 0 (Azure defaults can drift between CLI
versions):

```bash
az containerapp show --name baby-names-api --resource-group baby-names-rg \
  --query "properties.template.scale.minReplicas"
```

Get the app's URL for step 8:

```bash
az containerapp show --name baby-names-api --resource-group baby-names-rg \
  --query "properties.configuration.ingress.fqdn" -o tsv
```

Smoke-test:

```bash
curl -s "https://$(az containerapp show --name baby-names-api --resource-group baby-names-rg --query "properties.configuration.ingress.fqdn" -o tsv)/health"
```

## 6. Create the daily keepalive job

Same image, `keepalive` entrypoint instead of the default `uvicorn` command
(research §2). Pings the database directly, not through `/health`, so an
application bug in the web app can't also let the database lapse.

The container command is the `babynames-keepalive` console script
(`api/pyproject.toml`'s `[project.scripts]`), not `python -m
babynames_api.keepalive` — the installed `containerapp` extension's argument
parser treats any `--command`/`--args` token starting with `-` (like `-m`) as
an unrecognized flag rather than a value, silently dropping it. A
zero-argument entry point sidesteps the whole class of problem.

```bash
az containerapp job create \
  --name baby-names-keepalive \
  --resource-group baby-names-rg \
  --environment baby-names-env \
  --trigger-type Schedule \
  --cron-expression "0 9 * * *" \
  --replica-timeout 60 \
  --replica-retry-limit 1 \
  --image babynamesacr.azurecr.io/baby-names-api:latest \
  --registry-server babynamesacr.azurecr.io \
  --cpu 0.25 --memory 0.5Gi \
  --command "babynames-keepalive" \
  --secrets database-url="$DATABASE_URL" \
  --env-vars DATABASE_URL=secretref:database-url
```

`0 9 * * *` is 09:00 UTC daily — pick any fixed time; what matters is that it's
daily, not weekly (research §2's margin-for-failure reasoning). Verify recent
runs:

```bash
az containerapp job execution list --name baby-names-keepalive --resource-group baby-names-rg -o table
```

## 7. Configure the budget alert

FR-024 — any nonzero spend should be visible immediately, not discovered on an
invoice. This creates an $20/month budget (the owner-authorized ceiling for
this deploy) with alerts at 50/80/100% to the account email.

The installed `az consumption budget create` (preview command group) has no
`--notifications` flag, so notifications have to go through the ARM REST API
directly:

```bash
SUB_ID=$(az account show --query id -o tsv)
cat > /tmp/budget.json <<EOF
{
  "properties": {
    "category": "Cost",
    "amount": 20,
    "timeGrain": "Monthly",
    "timePeriod": {
      "startDate": "$(date -u +%Y-%m-01)T00:00:00Z",
      "endDate": "2030-01-01T00:00:00Z"
    },
    "notifications": {
      "Actual_GreaterThan_50_Percent": {"enabled": true, "operator": "GreaterThan", "threshold": 50, "contactEmails": ["cdqt98@gmail.com"], "thresholdType": "Actual"},
      "Actual_GreaterThan_80_Percent": {"enabled": true, "operator": "GreaterThan", "threshold": 80, "contactEmails": ["cdqt98@gmail.com"], "thresholdType": "Actual"},
      "Actual_GreaterThan_100_Percent": {"enabled": true, "operator": "GreaterThan", "threshold": 100, "contactEmails": ["cdqt98@gmail.com"], "thresholdType": "Actual"}
    }
  }
}
EOF
az rest --method put \
  --url "https://management.azure.com/subscriptions/${SUB_ID}/resourceGroups/baby-names-rg/providers/Microsoft.Consumption/budgets/baby-names-budget?api-version=2023-11-01" \
  --body @/tmp/budget.json
```

Steady-state cost target is **$0** (research §1/§2) — this budget is a safety
net, not an expectation.

## 8. Wire the frontend's build-time config

The deployed bundle needs `VITE_API_BASE_URL` (step 5's FQDN, with `https://`),
`VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` at **build** time, or it
silently falls back to an empty Supabase config and `http://localhost:8000` —
a green build that fails at runtime.

Set them as GitHub repository secrets (never commit the values):

```bash
gh secret set VITE_API_BASE_URL --body "https://<containerapp-fqdn-from-step-5>"
gh secret set VITE_SUPABASE_URL --body "$SUPABASE_URL"
gh secret set VITE_SUPABASE_ANON_KEY --body "$SUPABASE_ANON_KEY"
```

Then add them to the `env:` block of the `Build` step in **both**
`.github/workflows/azure-static-web-apps.yml` and
`azure-static-web-apps-staging.yml`, alongside the existing
`VITE_COMMIT_SHA`/`VITE_SITE_URL` stamping — see those files for the exact
block.

## 9. Backups

Because a paused-and-undeleted-in-time free Supabase project is a real failure
mode (research §2), take a periodic dump. Not automated — a manual habit until
a later spec adds real backup infrastructure:

```bash
pg_dump "$DATABASE_URL" -Fc -f "baby-names-backup-$(date +%Y%m%d).dump"
```

Store it somewhere off this machine. A monthly cadence is enough for a
two-person pre-release app.

## Validating the deploy (SC-009, quickstart.md scenario 11)

Follow steps 0–8 above on a clean checkout and confirm:

- The service responds at `/health` with `{"status":"ok","database":"ok"}`.
- `alembic current` (from step 3) shows the expected head revision.
- `select count(*) from names` matches 63,880 (step 4).
- `git log -p -- api/ secrets/ .github/` contains no credential value at any
  commit — `secrets/.env` was never committed, and steps 5/6/8 only ever
  reference secrets by name.
- The keepalive job's most recent execution (step 6) succeeded.
