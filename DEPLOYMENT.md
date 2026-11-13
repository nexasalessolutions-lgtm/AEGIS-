# GitHub-only development and preview

AEGIS is developed and previewed in GitHub Codespaces. This repository does not require an external application host for the interactive development preview.

## Start

1. Open [Create an AEGIS Codespace](https://codespaces.new/nexasalessolutions-lgtm/AEGIS-?ref=main).
2. Wait for the dev container to finish creating.
3. The post-start script builds and starts the local FastAPI API and isolated Slither worker, then launches Next.js.
4. Open the forwarded port labelled **AEGIS dashboard preview** (3000). Keep its visibility private.

## Runtime topology

- Next.js dashboard: port 3000.
- FastAPI gateway: port 8000.
- Private Slither worker: internal Docker Compose service on port 8001; it is not published to the internet.
- API-to-worker communication uses the internal Compose network.
- The browser talks to the API through a same-origin Next.js proxy.
- Random per-Codespace tokens are generated in the ignored `.env` file.

## Restart and diagnostics

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 api slither-worker
tail -n 100 .aegis-logs/next.log
```

Health checks:
- `http://localhost:3000`
- `http://localhost:8000/health`
- `http://localhost:8000/api/worker/health`

## Important limits

A Codespace is a development environment, not a permanent production server. It can stop when idle, and its compute/storage are subject to GitHub quotas. A forwarded preview URL works only while the Codespace is running and the port remains forwarded. GitHub Pages cannot host the FastAPI API or execute native security tools.

The scan queue is currently in-memory. Restarting the API loses active and recent jobs. Do not claim durable background processing until a persistent queue and database have been implemented and tested.

## Security

Keep forwarded ports private. Never expose the worker publicly. Never commit generated `.env` tokens or RPC credentials. Live-chain operations remain read-only. Static-analysis output and fork tests are evidence requiring review, not proof of exploitability.
