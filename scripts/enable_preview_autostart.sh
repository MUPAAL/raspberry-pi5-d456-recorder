#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TARGET_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
mkdir -p "$TARGET_DIR"
INSTALL_DIR="${D456_INSTALL_DIR:-$HOME/python_code}"
cat > "$TARGET_DIR/d456-recorder-preview.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=D456 Recorder Preview
Comment=Start the D456 recorder with a visible terminal and depth preview
Exec=x-terminal-emulator -e bash -lc '$INSTALL_DIR/run_preview.sh; status=\$?; echo; echo "Preview process exited with status \$status"; read -r'
Terminal=false
X-GNOME-Autostart-enabled=true
NoDisplay=false
EOF
echo "Desktop preview autostart enabled. Disable systemd first: sudo systemctl disable --now d456-monitor.service"

