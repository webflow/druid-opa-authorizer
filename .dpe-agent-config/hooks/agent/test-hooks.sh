#!/usr/bin/env bash
# Consumer-side: run the vendored test suite against the vendored hooks, and this repo's own
# local-rule tests if it has any.
set -euo pipefail
cd "$(dirname "$0")"
python3 -c 'import pytest' 2>/dev/null || { echo "pytest missing: pip install pytest (or: uv pip install pytest)" >&2; exit 1; }
python3 -m pytest -q tests/

# `lint` requires a test file beside every .agents/rules/<name>.py, so this runs them too -- a
# required test that never executes reads as coverage and is not. The root comes from this
# script's own location rather than git, which a tarball or a git-less image may not have; both
# layouts put this file three levels below it.
root="$(cd ../../.. && pwd)"
if [ -d "$root/.agents/rules/tests" ]; then
  echo "running local rule tests: .agents/rules/tests"
  # Both directories on the path: `helpers` resolves from here, the rule module from
  # .agents/rules, which is how the launcher loads them too.
  code=0
  PYTHONPATH="$PWD:$root/.agents/rules${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m pytest -q "$root/.agents/rules/tests" || code=$?
  # 5 is pytest's "no tests collected", which is not a failure here: a rule with no test is what
  # `lint` reports.
  [ "$code" -eq 0 ] || [ "$code" -eq 5 ] || exit "$code"
fi
