# 完整安装步骤

## 1. 烧录 Raspberry Pi OS

使用 Raspberry Pi Imager 烧录 64 位 Raspberry Pi OS。无显示器部署时，在 Imager 的系统定制页面完成：

- 创建用户名和密码；
- 配置 Wi-Fi 和国家/地区；
- 启用 SSH；
- 设置时区和主机名。

启动后连接：

```bash
ssh <用户名>@<主机名>.local
```

更新系统：

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

重新登录并确认 64 位系统：

```bash
uname -m
python3 --version
```

`uname -m` 应显示 `aarch64`。

## 2. 编译并安装 librealsense

本项目固定使用 `v2.59.2`。运行：

```bash
chmod +x scripts/build_librealsense.sh
./scripts/build_librealsense.sh
```

脚本使用 `FORCE_RSUSB_BACKEND=ON`，避免为 Raspberry Pi 当前内核打 RealSense 内核补丁。编译时间取决于 Pi 型号、内存和散热情况。

完成后重新插拔 D456，并检查：

```bash
rs-enumerate-devices
cd ~
python3 -c "import pyrealsense2 as rs; print('pyrealsense2 OK:', rs.__file__)"
```

不要只在 `~/librealsense/build` 内测试 Python 导入，否则可能误用编译目录中的临时模块。

## 3. 运行三路流测试

```bash
python3 scripts/smoke_test.py
```

预期结果：

```text
Camera: RealSense D456
Depth: True
Color: True
Infrared 1: True
```

单个中心像素为 `0.0 m` 不一定是故障；脚本还会报告有效像素比例和中位深度。

## 4. 安装录像程序

```bash
chmod +x scripts/install_recorder.sh
./scripts/install_recorder.sh
```

默认安装到：

```text
~/python_code/
```

默认数据目录：

```text
~/Pictures/farrow_data/
```

安装脚本只安装服务文件，不会立即启用后台服务。

## 5. 首次手动测试

```bash
cd ~/python_code
python3 -u D456_pig_recorder.py
```

等待程序完成至少一个 `:00` 或 `:30` 采集周期，然后按 `Ctrl+C` 安全停止。

检查文件：

```bash
find ~/Pictures/farrow_data -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' | sort
```

确认 RGB、DP、IR、IR_SN、DM 和 CALIBRATION 均符合预期后，再配置监控程序。

## 6. 手动测试监控程序

```bash
cd ~/python_code
python3 -u monitor_d456_rgb_recorder.py
```

另开一个 SSH 终端查看主录像日志：

```bash
tail -f ~/python_code/D456_recorder_output.log
```

健康文件应显示 `OK`：

```bash
cat ~/python_code/recorder_camera_health.status
```

## 7. 启用开机自动运行

确认手动测试没有问题后：

```bash
sudo systemctl enable --now d456-monitor.service
systemctl status d456-monitor.service --no-pager
```

重启验证：

```bash
sudo reboot
```

重新登录后：

```bash
systemctl status d456-monitor.service --no-pager
tail -n 100 ~/python_code/D456_recorder_output.log
```

## 8. 固件说明

本项目在 D456 固件 `5.16.0.1` 上已经完成三路流测试和实际录像。librealsense `v2.59.2` 发布说明推荐 D456 USB 使用 `5.17.3.10+`。

固件升级会写入相机内部存储，因此本仓库不自动下载或刷写固件。需要升级时，只使用官方固件和官方升级步骤，并确保全过程不断电、不拔线。

