#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_DIR="$SCRIPT_DIR/../server"

cd "$SERVER_DIR"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    "${EVOLVECLAW_PYTHON:-python3}" -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Starting EvolveClaw SCOPE server..."
exec python server.py
