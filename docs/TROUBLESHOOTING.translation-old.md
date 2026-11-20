# 常见问题排查

## `No module named 'cv2'` 或 `No module named 'scipy'`

```bash
sudo apt update
sudo apt install -y python3-opencv python3-scipy
```

检查所有依赖：

```bash
python3 - <<'PY'
import importlib

for name in ("pyrealsense2", "cv2", "numpy", "scipy", "gpiozero", "lgpio", "psutil"):
    try:
        module = importlib.import_module(name)
        print("OK", name, getattr(module, "__file__", "built-in"))
    except Exception as exc:
        print("MISSING", name, exc)
PY
```

## `pyrealsense2` 只在 build 目录中可以导入

```bash
cd ~/librealsense/build
sudo cmake --install .
sudo ldconfig
cd ~
python3 -c "import pyrealsense2 as rs; print(rs.__file__)"
```

## RealSense Viewer 报 GLX 1.3

RealVNC Virtual Mode 的虚拟 X 服务器可能不提供 Viewer 所需的 GLX。使用本仓库的无界面测试和日志检查即可；这不说明 SDK 或相机安装失败。

## 预览窗口为黑色

程序等待下一次采集时会关闭 D456 发射器，深度预览可能接近全黑。进入20秒采集阶段后发射器开启。后台服务模式不会显示预览窗口。

## `Health status write failed`

确保代码目录存在且当前用户可写：

```bash
mkdir -p ~/python_code
test -w ~/python_code && echo writable
```

当前仓库版本会自动创建健康状态文件所在目录。

## 监控程序运行后终端没有录像输出

这是预期行为。监控程序把录像程序输出重定向到：

```bash
tail -f ~/python_code/D456_recorder_output.log
```

## 中心深度为 `0.0 m`

第一帧、无效中心像素、距离过近、玻璃、黑色或反光目标都可能返回零。将相机对准约1–2米处的普通物体，使用 `scripts/smoke_test.py` 检查有效像素比例和中位深度。

## USB 或帧超时

- 使用 Raspberry Pi 5 的 USB 3 接口；
- 使用质量可靠的 USB 3 数据线；
- 不要通过无供电集线器连接；
- 使用 `rs-enumerate-devices` 确认 `Usb Type Descriptor` 为 3.x；
- 检查供电和散热。

## 查看最近错误

```bash
tail -n 100 ~/python_code/D456_recorder_output.log
tail -n 100 ~/python_code/monitor_d456_log.txt
journalctl -u d456-monitor.service -n 100 --no-pager
```

