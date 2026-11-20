# 运行与维护

## 采集计划

主程序保持 D456 流水线开启，在每个自然分钟的 `:00` 与 `:30` 开始一次20秒采集。等待期间发射器关闭，开始采集时打开。

默认状态：

- Arducam：关闭；
- VDA：关闭；
- 高帧率定时片段：关闭；
- D456 保存帧率：5 FPS；
- DM：每个片段保存一次。

## 服务控制

```bash
sudo systemctl start d456-monitor.service
sudo systemctl stop d456-monitor.service
sudo systemctl restart d456-monitor.service
systemctl status d456-monitor.service --no-pager
```

## 日志

监控程序日志：

```bash
tail -f ~/python_code/monitor_d456_log.txt
```

主录像程序日志：

```bash
tail -f ~/python_code/D456_recorder_output.log
```

systemd 日志：

```bash
journalctl -u d456-monitor.service -f
```

## 健康状态

```bash
cat ~/python_code/recorder_camera_health.status
```

正常内容包含：

```text
OK arducam_enabled=0 rgb=1 realsense=1
```

PID 文件只记录当前录像主进程编号，会在运行时自动创建和删除，不应提交到 GitHub：

```bash
cat ~/python_code/D456_rgb_recorder.pid
```

## 无显示器运行

通过 SSH 或 systemd 启动时，程序自动关闭 OpenCV 预览，但录像继续。监控程序没有完整图形界面，录像状态通过日志、健康文件和输出文件确认。

## 更改数据目录

临时运行：

```bash
D456_DATA_ROOT=/mnt/storage/farrow_data python3 -u ~/python_code/D456_pig_recorder.py
```

后台服务需要编辑 `/etc/systemd/system/d456-monitor.service` 中的 `D456_DATA_ROOT`，随后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart d456-monitor.service
```

## 升级代码

停止服务，备份配置，然后从新的仓库版本重新执行安装脚本：

```bash
sudo systemctl stop d456-monitor.service
./scripts/install_recorder.sh
sudo systemctl start d456-monitor.service
```

安装脚本不会删除已有录像数据。

