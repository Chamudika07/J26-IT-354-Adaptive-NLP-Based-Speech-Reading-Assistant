#!/bin/sh
# Run from any directory; this never loads or writes production data.
set -eu
cd "$(dirname "$0")/../apps/backend"
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest --cov=app --cov-report=term-missing
