#!/usr/bin/env bash
set -euo pipefail

# Creates a Python virtual environment in backend/.venv and installs requirements
# Usage:
#   From repo root: ./backend/setup_env.sh
#   Or set PYTHON to the interpreter you want: PYTHON=python3.11 ./backend/setup_env.sh


BASEDIR="$(cd "$(dirname "$0")" && pwd)"
# Create a venv directory named 'venv' so you can use: source venv/bin/activate
VENV_DIR="${VENV_DIR:-$BASEDIR/venv}"
PYTHON=${PYTHON:-python3}

echo "Creating virtual environment in $VENV_DIR using $PYTHON..."
$PYTHON -m venv "$VENV_DIR"

echo "Activating virtualenv and upgrading pip..."
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel

if [ -f "$BASEDIR/requirements.txt" ]; then
  echo "Installing requirements from $BASEDIR/requirements.txt..."
  pip install -r "$BASEDIR/requirements.txt"
else
  echo "No requirements.txt found in $BASEDIR; skipping installation."
fi

echo "Done. To activate the environment in future shells, run:"
echo "  source $VENV_DIR/bin/activate"

