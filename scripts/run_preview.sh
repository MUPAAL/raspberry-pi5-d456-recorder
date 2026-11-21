#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
INSTALL_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
if systemctl is-active --quiet d456-monitor.service; then
  echo "d456-monitor.service is active. Stop it first: sudo systemctl stop d456-monitor.service" >&2
  exit 1
fi
cd "$INSTALL_DIR"
exec /usr/bin/python3 -u D456_pig_recorder.py

