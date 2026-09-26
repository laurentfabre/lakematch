#!/usr/bin/env bash
# Run the test suite twice: a classic local session, then a local Spark Connect server. Exit 0 only if both pass.
set -u
cd "$(dirname "$0")/.."
source scripts/env.sh
rc=0
echo "== pass 1: classic session"
LAKEMATCH_TEST_CONNECT=0 python -m pytest "$@" || rc=1
echo "== pass 2: Spark Connect"
LAKEMATCH_TEST_CONNECT=1 python -m pytest "$@" || rc=1
exit $rc
