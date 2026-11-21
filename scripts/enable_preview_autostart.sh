#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TARGET_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
INSTALL_DIR="${D456_INSTALL_DIR:-$HOME/python_code}"
if [[ ! -f "$INSTALL_DIR/D456_pig_recorder.py" ]]; then
  echo "Install the recorder first: bash scripts/install_recorder.sh" >&2
  exit 1
fi
case "$INSTALL_DIR" in
  *[\"\$\`\\%]*|*$'\n'*)
    echo "The installation path contains unsupported desktop-entry characters." >&2
    exit 1
    ;;
esac
mkdir -p "$TARGET_DIR"
install -m 0755 "$REPO_ROOT/scripts/run_preview.sh" "$INSTALL_DIR/run_preview.sh"
cat > "$TARGET_DIR/d456-recorder-preview.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=D456 Recorder Preview
Comment=Start the D456 recorder with a visible terminal and depth preview
Exec=/bin/bash "$INSTALL_DIR/run_preview.sh"
Terminal=true
X-GNOME-Autostart-enabled=true
NoDisplay=false
EOF
echo "Desktop preview autostart enabled. Disable systemd first: sudo systemctl disable --now d456-monitor.service"

