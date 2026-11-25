#!/usr/bin/env bash
# Fast and full check (AGENTS.md "Commands"): lint, format check, type check and the tests,
# in the versions of requirements-dev.txt, as CI runs them. Runs them through uv, so nothing
# has to be installed beforehand.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
run() { uv run --quiet --no-project --with-requirements requirements-dev.txt -- "$@"; }
run ruff check .
run black --check --quiet .
run yamllint -d "{extends: relaxed, rules: {line-length: {max: 180}}}" .
run mypy
run python -m pytest -q tests
