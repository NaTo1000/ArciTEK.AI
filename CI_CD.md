# ArciTEK.AI CI/CD and Docker Compose Guide

This document describes the repository's continuous integration, container
delivery, and Docker Compose deployment process.

## Pipeline overview

The [CI/CD workflow](.github/workflows/ci.yml) runs for pull requests and
pushes to `main` or `develop`, for tags beginning with `v`, and when manually
started from GitHub Actions.

| Job | Purpose | Runs when |
| --- | --- | --- |
| `validate` | Compiles Python, runs the Python tests, lints JavaScript, builds the frontend, and uploads the browser bundle | Every workflow run |
| `container` | Builds the production image, validates Compose, starts the service, and checks `/api/health` | After validation succeeds |
| `publish` | Publishes the image to GitHub Container Registry (GHCR) and creates a provenance attestation | Pushes to `main` and `v*` tags |

Concurrency control cancels superseded runs on the same Git ref. The publish
job uses GitHub's `production` environment, so repository administrators can
configure required reviewers or deployment branch rules under **Settings →
Environments → production**.

## Image names and tags

Published images use:

```text
ghcr.io/nato1000/arcitek.ai
```

The workflow creates the following tags:

- `main` for the latest successful main-branch build.
- The semantic version and major/minor version for tags such as `v7.1.0`.
- `sha-<commit>` for traceability.

Package visibility and access are managed from the repository's GitHub
Packages settings. No registry credentials are stored in the repository; the
workflow uses its short-lived `GITHUB_TOKEN`.

## Local validation

Use the same commands as CI:

```bash
npm ci
python -m compileall -q arcitek_core
python -m unittest discover -s tests -p "test_*.py" -v
npm run lint
npm run build
docker build --tag arcitek-ai:local .
```

## Docker Compose quick start

Docker Compose requires an API token because the application listens on the
container's non-loopback interface. Generate a local token and export it
without writing it to source control:

```bash
export ARCITEK_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build --detach --wait
curl --fail http://127.0.0.1:8000/api/health
```

Open <http://127.0.0.1:8000> in a browser. Stop the service while preserving
its database:

```bash
docker compose down
```

To also delete the SQLite data volume:

```bash
docker compose down --volumes
```

## Configuration

Compose accepts these environment variables:

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ARCITEK_API_TOKEN` | Yes | None | Shared bearer credential for protected API routes |
| `ARCITEK_API_PRINCIPAL` | No | `compose-operator` | Audit identity assigned to API actions |
| `ARCITEK_WORKERS` | No | `2` | Compute worker count |
| `ARCITEK_BIND_ADDRESS` | No | `127.0.0.1` | Host address that publishes the service |
| `ARCITEK_BIND_PORT` | No | `8000` | Published host port |
| `ARCITEK_IMAGE` | No | `arcitek-ai:local` | Existing image to run instead of the local tag |

For example, run the image published from `main`:

```bash
export ARCITEK_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ARCITEK_IMAGE=ghcr.io/nato1000/arcitek.ai:main
docker compose pull
docker compose up --detach --wait --no-build
```

The service is bound to localhost by default. Before setting
`ARCITEK_BIND_ADDRESS=0.0.0.0`, place a TLS-enabled reverse proxy in front of
the application and restrict network access appropriately.

## Persistent data and security

The named volume `arcitek-data` stores `/app/data/arcitek.db`. Back up that
volume before upgrades that affect stored data.

The runtime container:

- Runs as an unprivileged `arcitek` user.
- Uses a read-only root filesystem and a bounded temporary filesystem.
- Drops all Linux capabilities and prevents privilege escalation.
- Stores writable application data only in the named volume.
- Exposes an unauthenticated health endpoint at `/api/health`; other API
  routes require the configured token in the `Authorization` header using the
  bearer authentication scheme.

Keep tokens in an environment-specific secret manager. Do not commit `.env`
files, tokens, exported Compose configurations, or database backups.

## Release process

1. Open a pull request against `main`.
2. Require the `validate` and `container` jobs in branch protection.
3. Merge only after both jobs pass.
4. Confirm that the `publish` job pushed the `main` image and attestation.
5. For a versioned release, create a semantic version tag such as `v7.1.0`.
6. Deploy the immutable version tag and verify `/api/health`.
7. Roll back by setting `ARCITEK_IMAGE` to the previous version and recreating
   the service.

Example deployment update:

```bash
export ARCITEK_IMAGE=ghcr.io/nato1000/arcitek.ai:7.1.0
docker compose pull
docker compose up --detach --wait --no-build
```

## Troubleshooting

### Compose reports that `ARCITEK_API_TOKEN` is missing

Export a non-empty token in the current shell before running any Compose
command, including `docker compose config`.

### The container is unhealthy

Inspect its status and logs:

```bash
docker compose ps
docker compose logs app
docker inspect --format '{{json .State.Health}}' arcitek-ai-app-1
```

Confirm that port `8000` is available and the data volume is writable by the
container's unprivileged user.

### GHCR pull is denied

Public packages can be pulled anonymously. For a private package, authenticate
with a classic personal access token that has `read:packages`, or use the
platform's workload identity:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io --username USERNAME --password-stdin
```

Never place the token directly in Compose YAML or shell history.

### A production publish is waiting

Review the `production` environment's protection rules. If required reviewers
are configured, an authorized reviewer must approve the job in GitHub Actions.
