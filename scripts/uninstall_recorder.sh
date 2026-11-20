#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
INSTALL_DIR="${D456_INSTALL_DIR:-$TARGET_HOME/python_code}"
SERVICE_NAME="d456-monitor.service"

sudo systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload

echo "The service was removed."
echo "Program files remain in $INSTALL_DIR and data was not deleted."
echo "Remove them manually only after making any required backup."

