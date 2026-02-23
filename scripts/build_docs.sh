#!/usr/bin/env bash
# Local doc build/serve script — mirrors .github/workflows/docs.yml
set -euo pipefail

COMMAND="${1:-serve}"  # 'build' or 'serve'

echo "[docs] Installing dependencies (--with docs)..."
poetry install --no-root --no-interaction --no-ansi --with docs

case "$COMMAND" in
  build)
    echo "[docs] Building MkDocs site..."
    poetry run mkdocs build
    echo "[docs] Site built at ./site/"
    ;;
  serve)
    echo "[docs] Starting local docs server at http://127.0.0.1:8080"
    poetry run mkdocs serve --dev-addr=127.0.0.1:8080
    ;;
  *)
    echo "Usage: $0 [build|serve]"
    exit 1
    ;;
esac
