# Baby Name Swipe

A two-parent baby-naming app: each swipes through a shared name deck independently,
and a match happens when both keep the same name. No backend — everything
persists in that device's browser storage. See `CLAUDE.md` for the full
architecture/feature spec.

## Stack

- Vite + React + TypeScript
- Inline styles throughout, no CSS framework in practice
- localStorage persistence, no accounts, no sync between devices

## Develop

```sh
npm install
npm run dev
```

## Build

```sh
npm run build   # tsc -b && vite build, output in dist/
npm run preview # serve the production build locally
```

## Deploy

Hosted on Azure Static Web Apps via the GitHub Actions workflows in
`.github/workflows/` — `azure-static-web-apps.yml` (prod, pushes to `main`)
and `azure-static-web-apps-staging.yml` (test, pushes to any other branch).
Each writes a `public/version.json` with the deploying commit's SHA and bakes
the same SHA into the build (`VITE_COMMIT_SHA`) for the in-app update-check
banner and the Settings page's build stamp.

## Domain

DNS for `baby-names.calebdudley.dev` (prod) and
`baby-names.test.calebdudley.dev` (test) is managed centrally in
[caleb-dudley-dev](../caleb-dudley-dev) via Terraform — see that repo's
README for the full project inventory and
`docs/adding-a-project.md` for how to change it.
