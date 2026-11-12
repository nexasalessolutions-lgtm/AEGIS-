# AEGIS API

FastAPI read-only intelligence API. Run locally with `pip install -r requirements.txt` then `uvicorn main:app --reload`. Endpoints: `/health`, `/api/chains`, `/api/protocols`, `/api/protocol/{slug}`, `/api/contract/inspect?chain=ethereum&address=0x...`, `/docs`.

Public RPCs are best-effort and rate-limited. Contract inspection only checks bytecode and attempts Sourcify lookup. It does not resolve proxies or prove vulnerabilities.
