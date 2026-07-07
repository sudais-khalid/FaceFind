# Deployment

Generated/audited by the `vibe-ship` skill. This project already had a working
local dev setup (`docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`)
before this pass - those were hardened in place rather than replaced, and a
genuinely separate production path was added alongside them.

## What changed

**Fixed in the existing dev setup** (still used for local development exactly
as before):
- `docker-compose.yml` had a hardcoded Postgres password (`password`) - now
  reads `POSTGRES_PASSWORD` from `.env` (default value unchanged, so nothing
  breaks; just no longer hardcoded in a file that could be committed).
- `backend/Dockerfile` ran as root with a single build stage - now a
  build/runtime multi-stage image with a non-root `appuser` and a real
  `HEALTHCHECK` against `/health`.
- `frontend/Dockerfile` (dev server) now runs as the non-root `node` user and
  has a `HEALTHCHECK`.
- The backend service's Docker healthcheck was running the **entire pytest
  suite** every 30 seconds instead of checking liveness - replaced with a
  lightweight request to `/health`.
- Added resource limits (`cpus`/`memory`) to every service.
- Added `.dockerignore` (root and `frontend/`) so `.git`, `.env`, `keys/`,
  `models/`, and test files never end up in a build context or image layer.

**New, for actual production deployment** (not used by local dev):
- `frontend/Dockerfile.prod` + `frontend/nginx.conf` - builds the real Vite
  bundle and serves it as static files via nginx (non-root, port 8080), since
  the dev Dockerfile just runs `vite dev` and was never meant to be deployed.
- `docker-compose.prod.yml` - the production stack: no bind mounts, no
  `--reload`, `db`/`redis` are not exposed to the host (internal network
  only), restart policies, and the nginx-served frontend image.
- `.github/workflows/ci-cd.yml` - lint (non-blocking) → unit tests (backend +
  frontend) → Trivy dependency scan (non-blocking) → build & push both
  production images to GHCR on `main`.

## Running locally (unchanged workflow)

```bash
docker compose up -d db redis   # or the full stack: docker compose up
```
Backend/frontend can still run locally outside Docker exactly as before
(`start.bat`, or `uvicorn`/`npm run dev` directly).

## Running the production stack

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```
Frontend is served on host port 80 (mapped to the container's unprivileged
8080). Set `PUBLIC_BASE_URL` in `.env` to wherever the backend will actually
be reachable from the browser before building - it's baked into the frontend
bundle at build time (Vite inlines `VITE_*` vars), not read at runtime.

## CI/CD

Push to `main` (or open a PR) to trigger `.github/workflows/ci-cd.yml`. No
extra secrets needed for the default path - it pushes to GHCR using the
built-in `GITHUB_TOKEN`. Set a `PUBLIC_BASE_URL` repository/environment
**variable** (Settings → Secrets and variables → Actions → Variables) if you
want the built frontend image to point at a real backend URL instead of
`localhost`.

## Manual follow-ups (not auto-fixed - these change app behavior)

- **CORS is scoped to `http://localhost:5173`** in `backend/app/main.py`.
  Correct for local dev; update to the real frontend origin before deploying
  publicly, or requests from the deployed frontend will be rejected.
- **Ports are hardcoded** (8000 backend, 8080/nginx frontend) rather than read
  from a `PORT` env var. Fine for Docker Compose; if you later deploy to a
  PaaS that assigns its own port (Render, Railway, Cloud Run), the Dockerfiles
  will need to read `$PORT` instead.
- **`db`/`redis` ports are still exposed to the host in the dev
  `docker-compose.yml`** (by design, for local `psql`/`redis-cli` access
  during development) - `docker-compose.prod.yml` does not expose them.
- The Trivy scan and `ruff` lint step in CI are set to non-blocking
  (`exit-code: 0` / `--exit-zero`) so adopting CI doesn't break the pipeline
  on day one. Flip both to blocking once existing findings are triaged.
