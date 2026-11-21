#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_GROUP="$(id -gn "$TARGET_USER")"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

if [[ -z "$TARGET_HOME" ]]; then
  echo "Could not determine the home directory for $TARGET_USER" >&2
  exit 1
fi

INSTALL_DIR="${D456_INSTALL_DIR:-$TARGET_HOME/python_code}"
DATA_DIR="${D456_DATA_ROOT:-$TARGET_HOME/Pictures/farrow_data}"
SERVICE_NAME="d456-monitor.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

sudo apt update
sudo apt install -y \
  python3-opencv python3-numpy python3-scipy \
  python3-gpiozero python3-lgpio python3-psutil

install -d -m 0755 "$INSTALL_DIR" "$DATA_DIR"
install -m 0644 "$REPO_ROOT/src/D456_pig_recorder.py" "$INSTALL_DIR/"
install -m 0644 "$REPO_ROOT/src/monitor_d456_rgb_recorder.py" "$INSTALL_DIR/"
if [[ -f "$REPO_ROOT/src/v4l2_sequence_capture.py" ]]; then
  install -m 0644 "$REPO_ROOT/src/v4l2_sequence_capture.py" "$INSTALL_DIR/"
fi
install -m 0755 "$REPO_ROOT/scripts/run_preview.sh" "$INSTALL_DIR/"

TEMP_SERVICE="$(mktemp)"
trap 'rm -f "$TEMP_SERVICE"' EXIT

sed \
  -e "s|@USER@|$TARGET_USER|g" \
  -e "s|@GROUP@|$TARGET_GROUP|g" \
  -e "s|@INSTALL_DIR@|$INSTALL_DIR|g" \
  -e "s|@DATA_DIR@|$DATA_DIR|g" \
  "$REPO_ROOT/systemd/d456-monitor.service.in" > "$TEMP_SERVICE"

sudo install -m 0644 "$TEMP_SERVICE" "$SERVICE_PATH"
sudo systemctl daemon-reload

echo
echo "Recorder installed in: $INSTALL_DIR"
echo "Data will be written to: $DATA_DIR"
echo
echo "First test it manually:"
echo "  cd '$INSTALL_DIR'"
echo "  python3 -u D456_pig_recorder.py"
echo
echo "After manual testing succeeds, enable the service:"
echo "  sudo systemctl enable --now $SERVICE_NAME"

