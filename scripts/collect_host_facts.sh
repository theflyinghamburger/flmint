#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

mkdir -p "$REPO_ROOT/reports"
"$PYTHON_BIN" -m flmint doctor --format text
"$PYTHON_BIN" -m flmint doctor --format json --save reports/host-audit.json

echo
echo "saved: reports/host-audit.json"