# AEGIS — DeFi Protocol Intelligence

Read-only DeFi protocol intelligence and smart-contract research workbench.

## Live app
- Dashboard: https://aegis-defi-intelligence.vercel.app
- API: https://aegis-api-v6-production.up.railway.app
- Health: https://aegis-api-v6-production.up.railway.app/health
- Worker health (through API): https://aegis-api-v6-production.up.railway.app/api/worker/health

## Implemented
- DeFiLlama protocol registry, TVL metadata, chain/category/search filters and protocol detail.
- Address candidate extraction with explicit unverified attribution.
- Read-only EVM inspection at a pinned block: bytecode, balance, nonce and EIP-1967 implementation/admin/beacon slots.
- Sourcify verified source, ABI and proxy-resolution metadata lookup.
- One-click protocol-to-contract discovery using DeFiLlama adapter source, public RPC bytecode verification and chain attribution.
- One-click automatic source retrieval from Sourcify, with Blockscout fallback where supported, followed by asynchronous private Slither analysis; the browser never receives scan credentials.
- Optional ZIP upload to the private Slither worker with archive validation, serialized execution and bounded runtime.
- Worker health endpoint reports Slither and solc versions.
- Foundry pinned-block read-only baseline harness.
- GitHub Actions CI for backend tests, frontend build, dependency audit and container builds.

## Repository
- `app/`: Next.js dashboard.
- `backend/main.py`: FastAPI gateway, protocol/contract intelligence, worker health and authenticated Slither forwarding.
- `backend/worker.py`: private Slither worker.
- `backend/Dockerfile`, `backend/Dockerfile.worker`: API and worker images.
- `foundry.toml`, `test/ForkBaseline.t.sol`: pinned fork baseline.
- `docker-compose.yml`: local API + isolated worker topology.
- `.github/workflows/ci.yml`: CI checks.

## Local development
Frontend: `npm install && npm run dev`.

API: `cd backend && pip install -r requirements-dev.txt && uvicorn main:app --reload`.

Worker: set `AEGIS_SCAN_TOKEN` and `AEGIS_WORKER_TOKEN` to separate strong secrets, then run `docker compose up --build`.

## Evidence policy and remaining work
Address candidates are not ownership claims. Verified source is not proof of correctness. Slither output is a static-analysis signal, not a confirmed vulnerability. Fork simulations at a pinned block do not alone prove current live exploitability.

The current scan-job registry is in-memory and jobs are lost if the API process restarts. Persistent queue, durable findings DB, complete protocol ownership attribution, full dependency graph, Aderyn/Mythril, protocol-specific fork reproduction, audit logs, multi-user tenancy and report signing/export are not yet production-enabled. Live-chain access remains read-only; no wallet signing, transaction submission or fund movement.
