#!/usr/bin/env bash
set -euo pipefail

SDK_VERSION="${SDK_VERSION:-v2.59.2}"
SOURCE_DIR="${LIBREALSENSE_SOURCE_DIR:-$HOME/librealsense}"
JOBS="${BUILD_JOBS:-2}"

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "Warning: this procedure was tested on aarch64 Raspberry Pi OS." >&2
fi

sudo apt update
sudo apt install -y \
  git cmake build-essential pkg-config \
  libssl-dev libusb-1.0-0-dev libudev-dev \
  libgtk-3-dev libglfw3-dev libgl1-mesa-dev libglu1-mesa-dev \
  python3-dev python3-numpy

if [[ -e "$SOURCE_DIR" ]]; then
  echo "Refusing to overwrite existing path: $SOURCE_DIR" >&2
  echo "Set LIBREALSENSE_SOURCE_DIR to a new path or remove it manually." >&2
  exit 1
fi

git clone --branch "$SDK_VERSION" --depth 1 \
  https://github.com/realsenseai/librealsense.git "$SOURCE_DIR"

cd "$SOURCE_DIR"
# Prompts for a key press when a camera is attached.
sudo ./scripts/setup_udev_rules.sh

# Without the official 5 A supply, the Pi 5 limits USB to 600 mA, which is
# not enough to open a RealSense camera reliably.
CONFIG_TXT=/boot/firmware/config.txt
if [[ -f "$CONFIG_TXT" ]] && ! grep -q '^usb_max_current_enable=1' "$CONFIG_TXT"; then
  printf '\n[all]\nusb_max_current_enable=1\n' | sudo tee -a "$CONFIG_TXT" > /dev/null
  echo "Added usb_max_current_enable=1 to $CONFIG_TXT (takes effect after reboot)."
fi

cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DFORCE_RSUSB_BACKEND=ON \
  -DBUILD_EXAMPLES=ON \
  -DBUILD_GRAPHICAL_EXAMPLES=ON \
  -DBUILD_PYTHON_BINDINGS=ON \
  -DPYTHON_EXECUTABLE=/usr/bin/python3

cmake --build build --parallel "$JOBS"
sudo cmake --install build
sudo ldconfig

echo
echo "librealsense installation finished."
echo "Reboot, then run: rs-enumerate-devices"
echo "Test Python outside the build directory:"
echo "  cd ~ && python3 -c \"import pyrealsense2 as rs; print(rs.__file__)\""

