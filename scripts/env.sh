#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cat <<ENVVARS
export DYLD_FRAMEWORK_PATH="$ROOT_DIR/.tools/python312"
export DYLD_LIBRARY_PATH="$ROOT_DIR/.tools/python312/Python.framework/Versions/3.12/lib"
export PYTHONHOME="$ROOT_DIR/.tools/python312/Python.framework/Versions/3.12"
ENVVARS
