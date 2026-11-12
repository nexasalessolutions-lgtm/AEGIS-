# AEGIS — DeFi Protocol Intelligence

Read-only DeFi protocol intelligence and smart-contract research workbench.

## Live app
- Dashboard: https://aegis-defi-intelligence.vercel.app
- API: https://aegis-api-v2-production.up.railway.app
- Health: https://aegis-api-v2-production.up.railway.app/health

## Implemented
- DeFiLlama protocol registry, TVL metadata, chain/category/search filters and protocol detail.
- Address candidate extraction with explicit unverified attribution.
- Read-only EVM inspection at a pinned block: bytecode, balance, nonce and EIP-1967 implementation/admin/beacon slots.
- Sourcify verified source, ABI and proxy-resolution metadata lookup.
- Authenticated ZIP upload to a private Slither worker with archive validation and bounded runtime.
- Foundry pinned-block read-only baseline harness.
- GitHub Actions CI for frontend build and backend tests.

## Repository
- `app/`: Next.js dashboard.
- `backend/main.py`: FastAPI gateway, protocol and contract intelligence, authenticated Slither forwarding.
- `backend/worker.py`: isolated Slither worker.
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

Persistent job queue, durable findings DB, complete protocol ownership attribution, full dependency graph, Aderyn/Mythril, protocol-specific fork reproduction, audit logs, multi-user tenancy and report signing/export are not yet production-enabled. Live-chain access remains read-only; no wallet signing, transaction submission or fund movement.
