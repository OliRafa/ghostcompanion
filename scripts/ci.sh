#!/usr/bin/env bash
#
# Single source of truth for CI. Runs the exact same checks locally (git hooks)
# and on GitHub Actions, so "passes locally" means "passes CI".
#
# Every caller runs the full pipeline — there is no partial mode on purpose.
#
# Usage:
#   scripts/ci.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

step() {
    printf '\n\033[1;34m▶ %s\033[0m\n' "$1"
}

step "Install dependencies"
poetry install --no-interaction

step "Check formatting with Black"
poetry run black --check .

step "Check import order with isort"
poetry run isort --check-only .

step "Lint with pylama"
poetry run pylama .

step "Run tests"
poetry run pytest

printf '\n\033[1;32m✔ CI passed\033[0m\n'
