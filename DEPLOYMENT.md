# Production deployment

## Hosted services
- Vercel dashboard: https://aegis-defi-intelligence.vercel.app
- Railway FastAPI gateway: https://aegis-api-v2-production.up.railway.app
- Railway read-only Bun API (fallback): https://aegis-read-api-production.up.railway.app
- Slither worker: private Railway service; no public domain.

## Railway API gateway
- Service: `aegis-api-v2`
- Repository: `nexasalessolutions-lgtm/AEGIS-`, branch `main`
- Root directory: `backend`
- Dockerfile: `Dockerfile`
- Health check: `/health`
- Railway container port: `8080`
- Variables already configured: `CORS_ORIGINS`, `AEGIS_WORKER_URL`, `AEGIS_WORKER_TOKEN`, `AEGIS_SCAN_TOKEN`.

## Slither worker
- Service: `aegis-slither-runner-v2`
- Root directory: `backend`
- Dockerfile: `Dockerfile.worker`
- Private endpoint: `aegis-slither-worker-v2.railway.internal:8001`
- Health check: `/health`
- `PORT=8001`
- `AEGIS_WORKER_TOKEN` is configured as a Railway variable and must match the API service's value.
- Keep this worker private. Do not add a public domain.

## Scan endpoint
`POST /api/scans/slither` on the API gateway accepts a ZIP archive of Solidity sources and a bearer token matching `AEGIS_SCAN_TOKEN`. The gateway forwards the archive to the private worker. The worker enforces a 20 MB upload cap, 100 MB expanded archive cap, 500-file cap, path traversal/symlink checks and a 180-second timeout. Static analysis does not prove exploitability.

## Secrets
The API scan token and internal worker token have been generated and stored in Railway variables. They are not committed to Git or embedded in the browser bundle. To run a scan from the dashboard, copy the API service's `AEGIS_SCAN_TOKEN` value from Railway Variables into the password field. Never paste the internal worker token into the browser.

## Remaining production requirements
Persistent scan queue, durable findings storage, multi-user authentication/tenancy, audit logs, backups, report signing/export, Aderyn/Mythril and protocol-specific Foundry/Anvil reproduction still require implementation and validation. No real transaction signing or broadcasting is supported.
