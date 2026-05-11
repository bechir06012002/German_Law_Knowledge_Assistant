#!/usr/bin/env bash
# Update the backend on the Hetzner server. Run from the repo root, on the server:
#
#   ./deploy/deploy.sh
#
# Deliberately boring: pull, rebuild, restart, prune, verify. No orchestration, no registry.

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f backend/.env ]]; then
    echo "backend/.env is missing — the container will start and then fail on the first"
    echo "request with a config error. Copy backend/.env.example and fill it in first."
    exit 1
fi

echo "==> pulling"
git pull --ff-only

echo "==> building and restarting"
cd backend
docker compose up -d --build

echo "==> pruning old layers"
# The image is ~2.5 GB and the box has a 40 GB disk; a few rebuilds of dangling layers fill
# it faster than you would expect.
docker image prune -f

echo "==> waiting for health"
for i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "    healthy after ${i}s"
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo "    never became healthy — check: docker compose logs --tail=50"
        exit 1
    fi
    sleep 1
done

cat <<'EOF'

Deployed. One thing left, and it is not optional:

  /health passing does NOT mean the model loaded. It is pulled in lazily on the first
  search, so a container that is out of memory still reports healthy and only dies when
  someone asks a real question.

  Ask a real question through the UI before calling this done.

  Disk check:  df -h /
  Memory:      docker stats --no-stream
EOF
