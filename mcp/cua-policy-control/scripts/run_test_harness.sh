#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL="${POGS_TEST_HARNESS_SKILL:-/openai/project/cua/.skills/pogs-test-harness/SKILL.md}"

if [[ ! -f "$SKILL" ]]; then
  echo "HARNESS_SKILL=FAIL missing $SKILL" >&2
  exit 2
fi

cd "$APP_ROOT"
export PYTHONPATH="$APP_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export CUA_MCP_TOKEN=""

python -m unittest -v tests.test_policy_bridge tests.test_mcp_harness

echo "HARNESS_SKILL=PASS"
echo "HARNESS_SOURCE=$SKILL"
echo "HARNESS_TARGET=$APP_ROOT"
