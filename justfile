set dotenv-load := false

# Run backend and frontend together; Ctrl-C stops both
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT
    just backend &
    just frontend &
    wait

# Install Python and frontend dependencies
setup:
    uv sync
    npm ci --prefix frontend
    test -f .env || cp .env.example .env

backend:
    uv run uvicorn backend.app:app --reload --env-file .env --host 127.0.0.1 --port 8000

frontend:
    npm run dev --prefix frontend

test:
    uv run python -m unittest discover -s tests -v
    npm run build --prefix frontend
