# AEGIS — DeFi Protocol Intelligence

Read-only DeFi protocol intelligence and smart-contract research workbench.

## Launch in GitHub Codespaces

[**Create an AEGIS Codespace**](https://codespaces.new/nexasalessolutions-lgtm/AEGIS-?ref=main)

The repository includes a Codespaces development container. On first creation it installs Node dependencies, starts the local FastAPI gateway and isolated Slither worker with Docker Compose, and launches the Next.js dashboard. Open the forwarded **AEGIS dashboard preview** port (3000) to use the app.

- Dashboard: forwarded Codespaces port 3000 (private by default).
- API: forwarded Codespaces port 8000 (private by default).
- API and Slither worker run inside the Codespace; they are not permanent public services.
- Codespaces compute and storage are subject to GitHub plan quotas and usage limits.
- The generated `.env` contains per-Codespace random scan tokens and is never committed.

## Implemented repository capabilities

- DeFiLlama protocol registry, TVL metadata, chain/category/search filters and protocol detail.
- Address candidate extraction with explicit unverified attribution.
- Read-only EVM inspection at a pinned block: bytecode, balance, nonce and EIP-1967 implementation/admin/beacon slots.
- Sourcify verified source, ABI and proxy-resolution metadata lookup.
- Protocol-to-contract discovery using DeFiLlama adapter source, public RPC bytecode verification and chain attribution.
- Source retrieval from Sourcify, with supported Blockscout fallback, followed by Slither analysis in a private worker.
- ZIP upload to the Slither worker with archive validation, serialized execution and bounded runtime.
- SQLite-backed scan job/result history with a 30-day retention policy and restart recovery for interrupted jobs.
- Foundry pinned-block read-only baseline harness.
- GitHub Actions CI for backend tests, frontend build, dependency audit and container builds.

## Architecture

- `app/`: Next.js dashboard and same-origin API proxy.
- `backend/main.py`: FastAPI gateway, protocol/contract intelligence and authenticated Slither forwarding.
- `backend/worker.py`: isolated Slither worker.
- `backend/Dockerfile`, `backend/Dockerfile.worker`: API and worker images.
- `docker-compose.yml`: local API + isolated worker topology.
- `.devcontainer/`: GitHub Codespaces setup and startup.
- `.github/workflows/ci.yml`: automated checks.

## Local development

In a Codespace, services are started automatically. To restart the API and worker:

```bash
docker compose up -d --build
```

To start the dashboard manually:

```bash
npm run dev -- --hostname 0.0.0.0
```

API health: `http://localhost:8000/health`.

## Evidence policy and remaining work

Address candidates are not ownership claims. Verified source is not proof of correctness. Slither output is a static-analysis signal, not a confirmed vulnerability. Fork simulations at a pinned block do not alone prove current live exploitability.

Scan job records and complete JSON results are stored in a Docker-managed SQLite volume for 30 days. The SQLite-backed queue resumes queued or interrupted jobs after an API restart on a single API instance. It is not a distributed multi-instance queue. Complete protocol ownership attribution, full dependency graph, Aderyn/Mythril, protocol-specific fork reproduction, audit logs, multi-user tenancy and signed reports are not yet production-enabled. Live-chain access remains read-only; no wallet signing, transaction submission or fund movement.

## Usage and security

Do not expose the API or worker ports publicly. Keep Codespaces ports private. Never commit `.env`, RPC credentials or scan tokens. Run contract-source analysis in the isolated worker; treat all source archives and tool output as untrusted.
