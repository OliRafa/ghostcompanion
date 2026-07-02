#!/usr/bin/env bash
# One-time setup: point git at the version-controlled hooks/ directory so the
# CI pipeline runs on every commit and push. Run once after cloning.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath hooks
echo "Git hooks enabled (core.hooksPath=hooks). scripts/ci.sh now runs on commit and push."
