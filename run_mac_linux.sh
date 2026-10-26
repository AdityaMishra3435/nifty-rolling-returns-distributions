#!/usr/bin/env bash
# One-click runner for macOS / Linux. Pass options through, e.g.:
#   ./run_mac_linux.sh --indices "NIFTY 50" "NIFTY 500"
set -e
cd "$(dirname "$0")"
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
if [ ! -d .venv ]; then
  echo "Creating virtual environment (first run only)..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
python run.py "$@"
