#!/bin/bash
# Run code quality checks (formatting) without modifying files.
# Exits non-zero if any check fails, e.g. for use in CI.
set -e

cd "$(dirname "$0")/.."

echo "Checking formatting with black..."
uv run black --check --diff backend/ main.py
