#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
eval "$("$ROOT_DIR/scripts/env.sh")"

PY312_BIN="$ROOT_DIR/.tools/python312/Python.framework/Versions/3.12/bin/python3.12"

if [[ ! -x "$PY312_BIN" ]]; then
  echo "[ERROR] Missing Python runtime: $PY312_BIN" >&2
  exit 1
fi

if [[ ! -d "$ROOT_DIR/.venv" ]]; then
  "$PY312_BIN" -m venv "$ROOT_DIR/.venv"
fi

"$ROOT_DIR/.venv/bin/pip" install -r "$ROOT_DIR/requirements.txt"

echo "[OK] venv ready at $ROOT_DIR/.venv"
