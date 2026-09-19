#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
exec "${LAKEMATCH_PYTHON:-.venv/bin/python}" -B tools/verify.py "${1:-}"
