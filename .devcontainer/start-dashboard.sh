#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p .aegis-logs

echo "[AEGIS] Checking dashboard dependencies..."
if [ ! -x node_modules/.bin/next ]; then
  echo "[AEGIS] Next.js is not installed; installing package dependencies..."
  npm install --no-audit --no-fund
fi

if [ ! -x node_modules/.bin/next ]; then
  echo "[AEGIS] ERROR: Next.js binary is still missing after npm install."
  echo "[AEGIS] package.json and npm install output should be checked."
  exit 1
fi

if curl -fsS --max-time 2 http://127.0.0.1:3000/ >/dev/null 2>&1; then
  echo "[AEGIS] Dashboard is already responding on port 3000."
  exit 0
fi

# Reuse an existing Next.js process if it is still starting; do not spawn duplicates.
if ! pgrep -f '[n]ext dev.*--hostname 0.0.0.0' >/dev/null 2>&1; then
  echo "[AEGIS] Starting Next.js on 0.0.0.0:3000..."
  nohup npm run dev -- --hostname 0.0.0.0 --port 3000 \
    >> .aegis-logs/next.log 2>&1 < /dev/null &
  echo "$!" > .aegis-logs/next.pid
fi

echo "[AEGIS] Waiting for dashboard HTTP response..."
for attempt in $(seq 1 90); do
  if curl -fsS --max-time 3 http://127.0.0.1:3000/ >/dev/null 2>&1; then
    echo "[AEGIS] Dashboard is responding: http://localhost:3000"
    exit 0
  fi
  if [ -f .aegis-logs/next.pid ] && ! kill -0 "$(cat .aegis-logs/next.pid)" 2>/dev/null; then
    echo "[AEGIS] ERROR: Next.js process exited during startup."
    break
  fi
  sleep 2
done

echo "[AEGIS] ERROR: Dashboard did not become healthy on port 3000."
echo "[AEGIS] Last Next.js log output:"
tail -n 100 .aegis-logs/next.log 2>/dev/null || true
exit 1
