#!/usr/bin/env bash
# Runs on the server as the chesso user. GitHub Actions triggers it over SSH
# after each push to main. Wrapped in main() so git pulling a new copy of this
# file mid-run can't change what bash executes.
main() {
  set -euo pipefail
  cd /home/chesso/chesso
  git fetch --quiet origin main
  git reset --quiet --hard origin/main
  echo "Deploying $(git log --oneline -1)"
  ~/.local/bin/uv sync --frozen --no-dev --quiet
  sudo /usr/bin/systemctl restart chesso
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/api/health/live >/dev/null 2>&1; then
      echo "Backend is healthy"
      exit 0
    fi
    sleep 2
  done
  echo "Backend did not become healthy" >&2
  sudo /usr/bin/journalctl -u chesso -n 40 --no-pager >&2 || true
  exit 1
}
main "$@"
