# Production deployment

## Hosted services
- Vercel dashboard: https://aegis-defi-intelligence.vercel.app
- Railway FastAPI gateway: https://aegis-api-v5-production.up.railway.app
- Private Slither worker: Railway service `aegis-slither-runner-v5`; no public domain.

## Railway API gateway
- Service: `aegis-api-v5`
- Repository: `nexasalessolutions-lgtm/AEGIS-`, branch `main`
- Root directory: `backend`
- Dockerfile: `Dockerfile`
- Health check: `/health`
- Railway container port: `8080`
- Variables: `CORS_ORIGINS`, `AEGIS_WORKER_URL`, `AEGIS_WORKER_TOKEN`, `AEGIS_SCAN_TOKEN`.

## Slither worker
- Service: `aegis-slither-runner-v5`
- Root directory: `backend`
- Dockerfile: `Dockerfile.worker`
- Private endpoint: `aegis-slither-worker-v5.railway.internal:8001`
- Health check: `/health`
- `PORT=8001`
- `AEGIS_WORKER_TOKEN` matches the internal token on the API service.
- Keep the worker private. Do not add a public domain.

## Scan endpoints
- `GET /api/worker/health` — reports private worker status, Slither version and Solidity compiler version.
- `POST /api/scans/slither` — optional ZIP upload, authenticated by the server-side `AEGIS_SCAN_TOKEN`.
- `POST /api/scans/protocol/{slug}` — starts automatic contract discovery, verified-source retrieval and Slither analysis; returns a job ID.
- `GET /api/scans/jobs/{jobId}` — polls an automatic scan job.

The worker enforces a 20 MB upload cap, 100 MB expanded archive cap, 500-file cap, path traversal/symlink checks, serialized execution and a 180-second timeout. It invokes a fixed Slither command. Static analysis does not prove exploitability.

## Secrets
The API scan token and internal worker token are stored in Railway variables. They are not committed to Git or embedded in the browser bundle. The Vercel server-side scan proxy stores `AEGIS_SCAN_TOKEN` as a sensitive project environment variable and forwards authenticated requests to the Railway API. The dashboard never asks the user to copy a token. The internal worker token is stored only in Railway service variables and must never be exposed to the browser. Automatic scan jobs are currently held in API-process memory; a Railway restart loses active and recent job state until a persistent queue/database is added.

## Remaining production requirements
Persistent scan queue, durable findings storage, multi-user authentication/tenancy, audit logs, backups, report signing/export, Aderyn/Mythril and protocol-specific Foundry/Anvil reproduction still require implementation and validation. No real transaction signing or broadcasting is supported.
