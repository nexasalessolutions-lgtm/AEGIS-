# AEGIS API

FastAPI read-only intelligence API with a combined Slither/Aderyn worker. Run locally with `pip install -r requirements.txt` then `uvicorn main:app --reload`. Endpoints: `/health`, `/api/chains`, `/api/protocols`, `/api/protocol/{slug}`, `/api/contract/inspect?chain=ethereum&address=0x...`, `/api/protocol/{slug}/contracts`, `/api/scans/protocol/{slug}`, `/api/scans/jobs/{jobId}`, `/api/scans/jobs`, `/ready`, `/docs`.

Public RPCs are best-effort and rate-limited. Contract inspection only checks bytecode and attempts Sourcify lookup. It does not resolve proxies or prove vulnerabilities.


Additional endpoints:
- `GET /api/protocol/{slug}/contracts` — inspect DeFiLlama adapter source, extract address candidates, and verify deployed bytecode on supported chains.
- `POST /api/scans/protocol/{slug}` — bounded multi-contract automatic scan: discover unique verified deployment candidates, retrieve Sourcify/Blockscout source bundles, and run Slither and Aderyn against up to 12 targets per protocol job. Requires the server-side scan token and is rate-limited.


## Durable scan records

Scan jobs and complete JSON results are persisted to SQLite. The Compose deployment mounts the named `aegis-data` volume at `/data`; records are retained for 30 days (maximum 1,000). Queued/running jobs are re-queued on API startup and resumed on a single API instance. This is not a distributed queue; do not run multiple API replicas against the same SQLite file.

The API exposes `/health` for liveness and `/ready` for database readiness. Compose health checks wait for the Slither worker and API readiness before considering services healthy.
