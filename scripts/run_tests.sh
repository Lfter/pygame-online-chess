#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
eval "$("$ROOT_DIR/scripts/env.sh")"

"$ROOT_DIR/.venv/bin/pytest"
