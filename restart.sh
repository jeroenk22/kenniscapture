#!/usr/bin/env bash
# Herstart alle Kenniscapture services

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$ROOT_DIR/stop.sh"

echo ""
echo "♻️  Herstarten..."
sleep 1

bash "$ROOT_DIR/start.sh"