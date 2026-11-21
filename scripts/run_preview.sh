#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR"
if [[ ! -f "$INSTALL_DIR/D456_pig_recorder.py" ]]; then
  INSTALL_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../src" && pwd)"
fi
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo "Run preview mode from a graphical desktop terminal." >&2
  exit 1
fi
if systemctl is-active --quiet d456-monitor.service; then
  echo "d456-monitor.service is active. Stop it first: sudo systemctl stop d456-monitor.service" >&2
  exit 1
fi
cd "$INSTALL_DIR"
exec /usr/bin/python3 -u D456_pig_recorder.py

