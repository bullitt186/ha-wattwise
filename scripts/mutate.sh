#!/usr/bin/env bash
# Mutation testing of wattwise.py with mutmut (settings: [tool.mutmut] in pyproject.toml).
#
# Usage:
#   scripts/mutate.sh            mutate wattwise.py if it changed against origin/main
#   scripts/mutate.sh --all      mutate wattwise.py regardless (the weekly workflow does this)
#   scripts/mutate.sh --results  list the surviving mutants of the last run
#
# Results are cached in mutants/; delete it to start over. MUTATE_BASE overrides the base.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
run() { uv run --quiet --no-project --with-requirements requirements-dev.txt -- "$@"; }
if [ -n "${MUTMUT_NO_UV:-}" ]; then run() { "$@"; }; fi

case "${1:-}" in
    --results) run mutmut results; exit 0 ;;
    --all) ;;
    "")
        base=$(git merge-base "${MUTATE_BASE:-origin/main}" HEAD)
        if git diff --quiet "$base" -- wattwise.py; then
            echo "wattwise.py did not change against ${MUTATE_BASE:-origin/main}; nothing to mutate."
            exit 0
        fi
        ;;
    *) echo "usage: scripts/mutate.sh [--all|--results]" >&2; exit 2 ;;
esac

run mutmut run
run mutmut export-cicd-stats
echo "Score: $(python3 -c 'import json; d = json.load(open("mutants/mutmut-cicd-stats.json")); t = d["killed"] + d["survived"] + d["timeout"] + d["suspicious"] + d["no_tests"]; print(f"{100 * (d["killed"] + d["timeout"]) / t:.1f}% of {t}" if t else "n/a")')"
echo "List the surviving mutants with 'scripts/mutate.sh --results'; inspect one with 'mutmut show <name>'."
