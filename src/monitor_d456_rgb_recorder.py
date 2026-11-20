## License: Apache 2.0. See LICENSE file in root directory.

"""Process-level watchdog for the standalone D456 recorder.

Camera stalls and disconnects are handled inside D456_pig_recorder.py. This
monitor only restarts the recorder's main process if that complete process
exits, and it does not mistake multiprocessing children for the main process.
"""

import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime

import psutil
from gpiozero import LED
from gpiozero.pins.lgpio import LGPIOFactory


PYTHON = sys.executable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDER_SCRIPT = os.environ.get(
    "D456_RECORDER_SCRIPT",
    os.path.join(SCRIPT_DIR, "D456_pig_recorder.py"),
)

MONITOR_LOG = os.environ.get(
    "D456_MONITOR_LOG",
    os.path.join(SCRIPT_DIR, "monitor_d456_log.txt"),
)
RECORDER_LOG = os.environ.get(
    "D456_RECORDER_LOG",
    os.path.join(SCRIPT_DIR, "D456_recorder_output.log"),
)
PID_FILE = os.environ.get(
    "D456_PID_FILE",
    os.path.join(SCRIPT_DIR, "D456_rgb_recorder.pid"),
)
HEALTH_STATUS_FILE = os.environ.get(
    "D456_HEALTH_STATUS_FILE",
    os.path.join(SCRIPT_DIR, "recorder_camera_health.status"),
)
HEALTH_STATUS_MAX_AGE_SECONDS = 2.0

START_DELAY_SECONDS = 10
CHECK_INTERVAL_SECONDS = 1

# Reboot only if the complete recorder crashes this many times inside the
# rolling time window. Camera subprocess restarts do not count here.
MAX_RESTARTS = 10
RESTART_WINDOW_SECONDS = 10 * 60


factory = LGPIOFactory()
red = LED(27, pin_factory=factory)

restart_times = deque()
shutdown_event = threading.Event()


def log(message):
    line = f"[{datetime.now().strftime('%F %T')}] {message}"
    print(line, flush=True)
    try:
        with open(MONITOR_LOG, "a", encoding="utf-8") as file:
            file.write(line + "\n")
    except Exception:
        pass


def write_pid(pid):
    try:
        with open(PID_FILE, "w", encoding="ascii") as file:
            file.write(str(pid))
    except Exception as exc:
        log(f"failed to write PID file: {exc}")


def read_pid():
    try:
        with open(PID_FILE, "r", encoding="ascii") as file:
            return int(file.read().strip())
    except Exception:
        return None


def remove_pid_file():
    try:
        os.unlink(PID_FILE)
    except FileNotFoundError:
        pass
    except Exception as exc:
        log(f"failed to remove PID file: {exc}")


def remove_health_file():
    try:
        os.unlink(HEALTH_STATUS_FILE)
    except FileNotFoundError:
        pass
    except Exception as exc:
        log(f"failed to remove health status file: {exc}")


def recorder_cameras_healthy():
    try:
        with open(HEALTH_STATUS_FILE, "r", encoding="ascii") as file:
            parts = file.read().strip().split()
        if len(parts) < 2 or parts[1] != "OK":
            return False
        return time.time() - float(parts[0]) <= HEALTH_STATUS_MAX_AGE_SECONDS
    except Exception:
        return False


def is_recorder_main_process(process):
    """Match the recorder even when Python options such as -u are present."""
    try:
        command = process.cmdline()
        if len(command) < 2:
            return False

        # Multiprocessing children use '-c ... spawn_main(...)' and must not
        # keep the recorder marked alive after the parent process exits.
        if any(arg in {"-c", "-m"} for arg in command[1:3]):
            return False
        if "--multiprocessing-fork" in command:
            return False

        expected = os.path.realpath(RECORDER_SCRIPT)
        return any(
            not arg.startswith("-") and os.path.realpath(arg) == expected
            for arg in command[1:]
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def find_recorder_main_process():
    pid = read_pid()
    if pid is not None:
        try:
            process = psutil.Process(pid)
            if process.is_running() and is_recorder_main_process(process):
                return process
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        remove_pid_file()

    for process in psutil.process_iter(["pid", "cmdline"]):
        if is_recorder_main_process(process):
            write_pid(process.pid)
            return process

    return None


def start_recorder():
    if find_recorder_main_process() is not None:
        log("D456 recorder main process already exists; duplicate start prevented")
        return True

    os.makedirs(os.path.dirname(RECORDER_LOG), exist_ok=True)
    remove_health_file()

    try:
        output = open(RECORDER_LOG, "ab", buffering=0)
        try:
            child_environment = os.environ.copy()
            child_environment["RECORDER_MONITOR_CONTROLS_RED"] = "1"
            process = subprocess.Popen(
                [PYTHON, "-u", RECORDER_SCRIPT],
                cwd=os.path.dirname(RECORDER_SCRIPT),
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
                env=child_environment,
            )
        finally:
            output.close()

        write_pid(process.pid)
        log(f"D456 recorder started, PID={process.pid}")
        return True
    except Exception as exc:
        log(f"failed to start D456 recorder: {exc}")
        remove_pid_file()
        return False


def stop_recorder():
    """Ask the recorder to stop both cameras and flush files before exit."""
    process = find_recorder_main_process()
    if process is None:
        remove_pid_file()
        return

    log(f"stopping D456 recorder, PID={process.pid}")
    try:
        process.terminate()  # SIGTERM is handled safely by the recorder.
        process.wait(timeout=35)
        log("D456 recorder stopped safely")
    except psutil.TimeoutExpired:
        log("recorder did not stop within 35 seconds; forcing process group stop")
        try:
            process_group = os.getpgid(process.pid)
            if process_group == process.pid:
                os.killpg(process_group, signal.SIGKILL)
            else:
                process.kill()
        except (ProcessLookupError, psutil.NoSuchProcess):
            pass
        except Exception as exc:
            log(f"forced recorder stop failed: {exc}")
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        pass
    finally:
        remove_pid_file()


def reboot_pi():
    log("restart limit reached; Raspberry Pi reboot requested")
    red.on()
    try:
        os.sync()
    except Exception:
        pass
    subprocess.run(["systemctl", "reboot"], check=False)


def register_restart():
    now = time.monotonic()
    while restart_times and now - restart_times[0] > RESTART_WINDOW_SECONDS:
        restart_times.popleft()
    restart_times.append(now)
    return len(restart_times)


def main():
    log("D456 recorder monitor started")

    def request_shutdown(signum, _frame):
        log(f"monitor received signal {signum}; stopping recorder")
        shutdown_event.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, request_shutdown)

    process = find_recorder_main_process()
    if process is None:
        red.on()
        start_recorder()
        shutdown_event.wait(START_DELAY_SECONDS)
    else:
        log(f"existing D456 recorder main process found, PID={process.pid}")

    try:
        while not shutdown_event.is_set():
            process = find_recorder_main_process()
            if process is not None:
                if recorder_cameras_healthy():
                    red.off()
                else:
                    red.on()
                shutdown_event.wait(CHECK_INTERVAL_SECONDS)
                continue

            red.on()
            remove_pid_file()
            remove_health_file()
            restart_count = register_restart()
            log(
                "D456 recorder main process is not running; "
                f"restart {restart_count}/{MAX_RESTARTS} "
                f"within {RESTART_WINDOW_SECONDS} seconds"
            )

            if restart_count >= MAX_RESTARTS:
                reboot_pi()
                shutdown_event.wait(60)
                restart_times.clear()
                continue

            start_recorder()
            shutdown_event.wait(START_DELAY_SECONDS)

    except KeyboardInterrupt:
        log("D456 recorder monitor stopped by user")
    finally:
        stop_recorder()
        red.off()
        red.close()


if __name__ == "__main__":
    main()

