#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p .aegis-logs

# Create private, per-Codespace development credentials. This file is gitignored.
if [ ! -f .env ]; then
  SCAN_TOKEN="$(openssl rand -hex 32)"
  WORKER_TOKEN="$(openssl rand -hex 32)"
  cat > .env <<EOF
AEGIS_SCAN_TOKEN=${SCAN_TOKEN}
AEGIS_WORKER_TOKEN=${WORKER_TOKEN}
AEGIS_WORKER_URL=http://slither-worker:8001
AEGIS_INTERNAL_API_URL=http://127.0.0.1:8000
EOF
  chmod 600 .env
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

echo "Waiting for the Codespaces Docker engine..."
for attempt in $(seq 1 60); do
  if docker info >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    echo "Docker did not become ready. Check the Codespaces Docker feature and try: docker info"
    exit 1
  fi
  sleep 2
done

echo "Building and starting the isolated API + Slither/Aderyn worker..."
docker compose up -d --build

if ! curl -fsS http://127.0.0.1:8000/ready >/dev/null 2>&1; then
  echo "Waiting for the AEGIS API..."
  for attempt in $(seq 1 180); do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then break; fi
    sleep 2
  done
fi

bash .devcontainer/start-dashboard.sh

echo
echo "AEGIS services requested."
echo "Dashboard: http://localhost:3000"
echo "API health: http://localhost:8000/health"
echo "Logs: .aegis-logs/next.log and docker compose logs"
