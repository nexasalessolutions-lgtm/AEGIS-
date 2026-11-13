# AEGIS architecture — GitHub-only workspace

## Runtime

- Next.js dashboard in the GitHub Codespace on port 3000.
- Same-origin Next.js API proxy forwards read-only browser requests to the local FastAPI gateway.
- FastAPI gateway runs in Docker Compose on port 8000.
- Slither worker runs as a private Docker Compose service on the internal network; it has no published port.
- DeFiLlama supplies protocol metadata and TVL.
- Public EVM RPC endpoints supply read-only chain state.
- Sourcify supplies verified-source metadata; supported Blockscout explorers are fallback sources.

## Isolated static-analysis worker

The worker accepts ZIP source bundles only, enforces archive size and path traversal checks, requires bearer authentication, invokes a fixed Slither command, and has a hard timeout. The Compose configuration uses a read-only filesystem, non-root identity, dropped capabilities, no-new-privileges, resource limits and an internal-only worker network.

## GitHub Codespaces

The `.devcontainer` definition configures Docker-in-Docker, forwards the private dashboard and API ports, installs Node dependencies, and starts the API, worker and dashboard. Per-Codespace secrets are generated locally in an ignored `.env` file. The preview is temporary and runs only while the Codespace is active.

## Evidence labels

- Registry metadata: third-party metadata, not protocol attestation.
- Bytecode/proxy slots: observed on-chain facts at the returned block.
- Verified source: source verification metadata, not correctness.
- Slither: static-analysis signal, not confirmed vulnerability.
- Fork reproduction: local simulation at a pinned block, not proof of current live exploitability.

## Not yet production-enabled

Persistent scan queue, durable findings storage, authenticated multi-user tenancy, complete protocol-to-contract attribution, verified-source dependency graph, Aderyn, Mythril, automated protocol-specific Foundry/Anvil reproduction, report signing/export and audit logging remain unfinished. Do not present these as live features until implemented and tested. Live-chain access remains read-only.
