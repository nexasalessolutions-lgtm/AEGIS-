# Production deployment guide

## Current hosted components
- Vercel hosts the Next.js dashboard.
- Railway hosts the Bun read-only API.
- The Python FastAPI gateway and Slither worker are implemented in this repository but are not yet attached to the live Railway services.

## Railway repository connection prerequisite
The Railway GitHub integration currently reports that it cannot access this repository. In Railway, connect/re-authorize the GitHub App and grant access to `nexasalessolutions-lgtm/AEGIS-`. Then create or attach services from branch `main`.

## API service
- Repository: `nexasalessolutions-lgtm/AEGIS-`
- Branch: `main`
- Root directory: `backend`
- Builder: Dockerfile
- Dockerfile path: `Dockerfile`
- Health check: `/health`
- Port: `8000`
- Variables:
  - `CORS_ORIGINS=https://aegis-defi-intelligence.vercel.app`
  - `AEGIS_WORKER_URL=http://aegis-slither-worker.railway.internal:8001`
  - `AEGIS_WORKER_TOKEN=<generate a unique random secret>`
  - `AEGIS_SCAN_TOKEN=<generate a separate random secret>`

## Slither worker service
- Same repository and branch.
- Root directory: `backend`
- Dockerfile path: `Dockerfile.worker`
- Health check: `/health`
- Port: `8001`
- Set `AEGIS_WORKER_TOKEN` to the same secret configured on the API service.
- Keep the worker private; do not create a public domain. Configure its private networking endpoint as `aegis-slither-worker`.

The API's private worker URL should then be `http://aegis-slither-worker.railway.internal:8001`.

## Frontend
The Vercel production deployment is already live. The current dashboard does not expose the authenticated Slither upload form yet; do not publish the worker token in browser code. The API gateway's `POST /api/scans/slither` route requires a bearer token and forwards the ZIP to the private worker.

## Secrets and cost
Generate secrets in a password manager or platform secret manager; do not commit them. Use public RPCs and free public metadata sources initially. Review Railway/Vercel usage limits before enabling more replicas, databases, or long-running jobs.

## Go-live checklist
- [ ] Railway GitHub App can read the repository.
- [ ] API and worker Docker images build from the checked-in Dockerfiles.
- [ ] API and worker health checks pass.
- [ ] Worker has no public domain and is reachable only over private networking.
- [ ] Both API and worker secrets are independently generated and configured.
- [ ] Upload size, timeout, archive path, and resource limits are verified.
- [ ] CI passes on the current main commit.
- [ ] Scanner output is reviewed as static-analysis signals, not confirmed vulnerabilities.
- [ ] A protocol-specific fork test is pinned to an exact chain block and RPC endpoint.
- [ ] Findings storage, user auth, tenancy, audit logging, backups, and retention are configured before multi-user production use.
