# Raspberry Pi 5 + RealSense D456 Recorder

面向无显示器 Raspberry Pi 5 的 Intel RealSense D456 定时采集与自动监控项目。

## 当前功能

- D456 持续连接，每个自然分钟的 `:00` 和 `:30` 开始一次采集。
- 每次保存 20 秒的 RGB、深度伪彩色视频和红外视频。
- 在打开发射器前保存一张 IR 快照。
- 保存相机标定信息和 DM 点云 MAT 数据。
- 相机卡死或子进程退出时自动重启采集子进程。
- 主录像程序异常退出时由监控程序重启。
- 支持无显示器、SSH 和 systemd 后台运行。

本仓库的默认部署配置为：

```python
ENABLE_ARDUCAM = False
ENABLE_HIGH_RATE_CLIPS = False
RECORD_VDA = False
```

`v4l2_sequence_capture.py` 仅在以后重新启用 Arducam 时使用。

## 已测试环境

- Raspberry Pi 5，64 位 Raspberry Pi OS / Debian 13
- Python 3.13
- RealSense D456，USB 3.2
- librealsense `v2.59.2`，RSUSB 后端
- D456 固件 `5.16.0.1`：本项目实际采集测试通过

librealsense `v2.59.2` 的发布说明推荐 D456 USB 使用固件 `5.17.3.10` 或更新版本。固件更新不是自动安装步骤，升级前应阅读官方说明，并确保相机和树莓派不会断电。

## 快速导航

1. [完整安装步骤](docs/INSTALL_ZH.md)
2. [运行、日志与停止](docs/OPERATIONS_ZH.md)
3. [常见问题排查](docs/TROUBLESHOOTING_ZH.md)

克隆仓库：

```bash
git clone https://github.com/Yu-Andy-Wang/raspberry-pi5-d456-recorder.git
cd raspberry-pi5-d456-recorder
```

## 仓库结构

```text
src/
  D456_pig_recorder.py
  monitor_d456_rgb_recorder.py
  v4l2_sequence_capture.py
scripts/
  build_librealsense.sh
  install_recorder.sh
  uninstall_recorder.sh
  smoke_test.py
systemd/
  d456-monitor.service.in
docs/
```

## 数据目录

默认保存到当前用户的：

```text
~/Pictures/farrow_data/
```

可以通过环境变量覆盖：

```bash
export D456_DATA_ROOT=/path/to/data
```

录像和标定文件可能包含设备序列号与实验数据，默认不会被 Git 跟踪。不要把实际数据目录提交到公共仓库。

## 重要说明

- 请将 D456 直接连接到 Raspberry Pi 5 的 USB 3 接口。
- RealSense Viewer 在 RealVNC Virtual Mode 中可能因缺少 GLX 1.3 无法启动；这不影响无界面的 Python 采集。
- 首次测试应直接运行主程序。确认录像正常后，再启用监控服务。
- 监控程序会把主程序输出写入日志，因此后台运行时不会出现完整录像界面。

## 上游资料

- [Raspberry Pi 无显示器安装](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [librealsense Linux 安装说明](https://github.com/realsenseai/librealsense/blob/master/doc/installation.md)
- [librealsense RSUSB 后端说明](https://github.com/realsenseai/librealsense/blob/master/doc/installation_jetson.md)
- [librealsense v2.59.2](https://github.com/realsenseai/librealsense/releases/tag/v2.59.2)

## 许可证

[MIT License](LICENSE)

