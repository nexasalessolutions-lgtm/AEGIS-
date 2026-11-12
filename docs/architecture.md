# AEGIS architecture and deployment

## Current deployed slice
- Next.js dashboard on Vercel.
- Read-only EVM/protocol metadata API on Railway Bun Functions.
- DeFiLlama for protocol metadata and TVL.
- Public EVM RPCs for read-only state.
- Sourcify for verified-source lookup.
- EIP-1967 implementation/admin/beacon slot inspection.

## Isolated static-analysis worker
The Slither worker in backend/worker.py accepts ZIP source bundles only, enforces archive limits and path traversal checks, requires bearer authentication, invokes a fixed Slither command, and has a hard timeout. backend/Dockerfile.worker builds the worker image. docker-compose.yml configures a read-only filesystem, non-root identity, dropped capabilities, no-new-privileges, resource limits, and disabled worker network access.

Run locally: set AEGIS_WORKER_TOKEN to a long random secret, then run docker compose up --build. API docs are at localhost:8000/docs; worker health is localhost:8001/health.

## Evidence labels
- Registry metadata: third-party metadata, not protocol attestation.
- Bytecode/proxy slots: observed on-chain facts at the returned block.
- Verified source: source verification metadata, not correctness.
- Slither: static-analysis signal, not confirmed vulnerability.
- Fork reproduction: local simulation at a pinned block, not proof of current live exploitability.

## Not yet production-enabled
Persistent scan queue, authenticated multi-user tenancy, durable database, complete protocol-to-contract attribution, verified-source dependency graph, deployed Slither job orchestration, Aderyn, Mythril, Foundry/Anvil fork runner, report export/signing, and audit logging remain unfinished. Do not present these as live features until deployed and tested.
