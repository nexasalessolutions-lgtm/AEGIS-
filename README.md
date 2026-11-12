# AEGIS — DeFi Protocol Intelligence

AEGIS is a read-only DeFi protocol intelligence and security research workbench.

## Live deployment

- Dashboard: https://aegis-defi-intelligence-nexaaisupportbusiness-3240.vercel.app
- Railway read API: https://aegis-read-api-production.up.railway.app
- Health: https://aegis-read-api-production.up.railway.app/health

## Current live capabilities

- DeFiLlama protocol registry, chain/category filtering, TVL metadata and protocol detail lookup.
- Address candidate extraction from provider protocol payloads. These are explicitly **unverified candidates**, not protocol ownership claims.
- Public EVM RPC inspection: runtime bytecode, latest block, balance, transaction count and EIP-1967 implementation/admin/beacon storage slots.
- Sourcify verified-source lookup.
- Read-only live-chain policy: no wallet signing, transaction submission, fund movement or exploit execution.

## Repository layout

- `app/`: Next.js dashboard.
- `backend/main.py`: FastAPI API gateway and local development API.
- `backend/worker.py`: authenticated Slither static-analysis worker.
- `backend/Dockerfile.worker`: worker container.
- `docker-compose.yml`: local API + isolated worker topology.
- `.github/workflows/ci.yml`: frontend build and backend tests.

## Local development

Frontend: `npm install && npm run dev`.

Backend: `cd backend && pip install -r requirements.txt && uvicorn main:app --reload`.

Worker stack: set `AEGIS_SCAN_TOKEN` and `AEGIS_WORKER_TOKEN` to independent long random secrets, then run `docker compose up --build`. The worker has a private-only network, no external egress, a read-only filesystem, dropped Linux capabilities, resource limits, archive path validation, upload size limits and execution timeout.

## Important security status

The Slither worker implementation and API gateway route are in the repository, but the worker is **not yet deployed or connected to the live Railway Bun API**. Persistent scan jobs, multi-user auth/tenancy, durable findings storage, complete protocol-to-contract attribution, source dependency graph, Aderyn, Mythril, Foundry/Anvil fork runner, audit logs and report signing/export are not yet production-enabled.

Static analysis is a review signal, not a confirmed vulnerability. Fork tests are local simulations at a specified block and do not alone prove current live exploitability. All live-chain access remains read-only.
