# AEGIS API

FastAPI read-only intelligence API. Run locally with `pip install -r requirements.txt` then `uvicorn main:app --reload`. Endpoints: `/health`, `/api/chains`, `/api/protocols`, `/api/protocol/{slug}`, `/api/contract/inspect?chain=ethereum&address=0x...`, `/api/protocol/{slug}/contracts`, `/api/scans/protocol/{slug}`, `/api/scans/jobs/{jobId}`, `/docs`.

Public RPCs are best-effort and rate-limited. Contract inspection only checks bytecode and attempts Sourcify lookup. It does not resolve proxies or prove vulnerabilities.


Additional endpoints:
- `GET /api/protocol/{slug}/contracts` — inspect DeFiLlama adapter source, extract address candidates, and verify deployed bytecode on supported chains.
- `POST /api/scans/protocol/{slug}` — one-contract automatic scan: discover candidate, retrieve one Sourcify-verified source bundle, then run Slither in the private worker. Requires the server-side scan token and is rate-limited.
