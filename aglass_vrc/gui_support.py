"""GUI settings and process control. No Tk or hardware work on import."""
from collections import deque
import contextlib
import ctypes as C
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from .cli import parse_args
from .gui_runner import EVENT_PREFIX
from .app_paths import application_root, worker_command

ROOT = application_root()
SETTINGS_PATH = ROOT / "aglass-gui.json"
DEFAULTS = {
    "connection": "sdk", "runtime_port": "0",
    "profile": "auto", "dll": "", "client_schema": "auto", "legacy_success_code": "auto",
    "use_running_runtime": False, "soft_dongle": False,
    "target": "native", "host": "127.0.0.1", "port": "9000", "parameter_prefix": "v2",
    "projection": "auto", "gaze_space": "viewport", "output": "center",
    "fov_x": "100", "fov_y": "100", "center_x": "0.5", "center_y": "0.5",
    "gain_x": "1", "gain_y": "1", "invert_x": False, "invert_y": False,
    "rate": "60", "smoothing_ms": "25", "stale_seconds": "0.25", "blink": True,
    "blink_delay_ms": "30", "blink_max_seconds": "0.6", "simulate": False, "dry_run": False,
    "runtime_host": "127.0.0.1", "runtime_send_port": "2000", "runtime_recv_port": "2001",
    "event_port": "2002", "data_port": "2003", "timeout": "5",
    "sdk_start_timeout": "30", "sdk_stop_timeout": "3", "log": "",
    "key_file": "", "key_image": "", "key_medium": "cdrom", "key_backend": "auto", "key_usbip": "",
}
KEY_SETTINGS = {"key_file", "key_image", "key_medium", "key_backend", "key_usbip"}


def load_settings(path=SETTINGS_PATH):
    if not path.exists():
        return DEFAULTS.copy()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") not in (1, 2) or not isinstance(data.get("settings"), dict):
        raise ValueError("设置文件格式不正确，请重新保存设置。")
    values = DEFAULTS.copy()
    for key, value in data["settings"].items():
        if key in values:
            if type(value) is not type(values[key]):
                raise ValueError(f"设置项 {key} 的类型不正确。")
            values[key] = value
    # Version 1 used SteamVR as the mandatory default, including on desktop.
    # Keep panel correction explicit; version 2 preserves new strict selections.
    if data["version"] == 1 and values["projection"] == "steamvr" and values["gaze_space"] == "viewport":
        values["projection"] = "auto"
    return values


def save_settings(values, path=SETTINGS_PATH):
    data = {key: values[key] for key in DEFAULTS}
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"version": 2, "settings": data}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_arguments(values, diagnose=False):
    argv = ["--sdk-isolation", "process"]
    for key, default in DEFAULTS.items():
        if key in KEY_SETTINGS:
            continue
        value = values[key]
        flag = "--" + key.replace("_", "-")
        if values["connection"] == "runtime" and key in ("dll", "profile", "use_running_runtime", "soft_dongle", "client_schema", "legacy_success_code"):
            continue  # Keep SDK settings saved, but do not apply them to direct TCP/UDP.
        if key == "dll" and values["use_running_runtime"]:
            continue  # Retain the saved manual path, but do not pass it to this session.
        if key == "blink":
            argv += [flag, "validity" if value else "off"]
        elif isinstance(default, bool):
            if value:
                argv.append(flag)
        elif key == "legacy_success_code" and value == "auto":
            continue
        elif key in ("dll", "log") and not value.strip():
            continue
        else:
            argv += [flag, value.strip()]
    if diagnose:
        argv.append("--diagnose")
    output = io.StringIO()
    with contextlib.redirect_stderr(output):
        try:
            args = parse_args(argv)
        except SystemExit as exc:
            raise ValueError(output.getvalue().split("error:")[-1].strip()) from exc
    if args.dll and (diagnose or not args.simulate) and not args.dll.is_file():
        raise ValueError("所选 DLL 不存在，请重新选择文件，或留空自动查找。")
    if args.log and not diagnose:
        if args.log.exists():
            raise ValueError("CSV 日志文件已存在。请选择新的文件名，防止覆盖旧记录。")
        if not args.log.parent.is_dir():
            raise ValueError("CSV 日志所在目录不存在。")
    if args.target == "vrcft-module" and args.host not in ("127.0.0.1", "localhost"):
        raise ValueError("VRCFT 模块仅接收本机数据，请使用 127.0.0.1。")
    if not args.host:
        raise ValueError("请填写 OSC 接收地址。")
    return argv


def python_executable():
    # pythonw has no useful stdout/stderr; the worker uses python.exe with NO_WINDOW.
    selected = Path(sys.executable)
    if selected.name.lower() == "pythonw.exe":
        selected = selected.with_name("python.exe")
    return str(selected)


def build_key_arguments(values, probe=False):
    backend = values["key_backend"]
    if backend not in ("auto", "wdm", "win2"):
        raise ValueError("请选择支持的 USB Key 驱动。")
    extra = ["--backend", backend] if backend != "auto" else []
    if values["key_usbip"].strip():
        extra += ["--usbip", values["key_usbip"].strip()]
    if probe:
        return ["--gui", "--probe", *extra]
    from .usbkey_device import TRACE
    key = Path(values["key_file"].strip()) if values["key_file"].strip() else TRACE
    image = values["key_image"].strip()
    medium = values["key_medium"]
    if medium not in ("cdrom", "disk"):
        raise ValueError("请选择光驱或磁盘形态。")
    if not key.is_file():
        raise ValueError("Key 应答文件不存在；留空可使用内置记录。")
    if image and not Path(image).is_file():
        raise ValueError("介质镜像文件不存在；留空可使用空白只读介质。")
    return ["--gui", "--key", str(key), "--medium", medium, *extra] + (["--image", image] if image else [])


class WindowsJob:
    """The GUI owns only its bridge and descendants, never the user's Runtime.

    Microsoft: https://learn.microsoft.com/windows/win32/procthread/job-objects
    A start handshake prevents the bridge from spawning before assignment.
    """
    def __init__(self):
        from ctypes import wintypes as W

        class Basic(C.Structure):
            _fields_ = [("per_process", C.c_int64), ("per_job", C.c_int64), ("flags", W.DWORD),
                        ("min_working", C.c_size_t), ("max_working", C.c_size_t), ("active", W.DWORD),
                        ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]

        class IO(C.Structure):
            _fields_ = [(name, C.c_uint64) for name in ("read_ops", "write_ops", "other_ops", "read", "write", "other")]

        class Extended(C.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_mem", C.c_size_t),
                        ("job_mem", C.c_size_t), ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]

        self.api = C.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [C.c_void_p, W.LPCWSTR]
        self.api.CreateJobObjectW.restype = W.HANDLE
        self.api.SetInformationJobObject.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]
        self.api.SetInformationJobObject.restype = W.BOOL
        self.api.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
        self.api.AssignProcessToJobObject.restype = W.BOOL
        self.api.CloseHandle.argtypes = [W.HANDLE]
        self.api.CloseHandle.restype = W.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)):
            error = C.WinError(C.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise C.WinError(C.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


class BridgeSession:
    def __init__(self, module="aglass_vrc.gui_runner", timeout_message=None, *, graceful_only=False):
        self.module = module
        self.graceful_only = graceful_only
        self.timeout_message = timeout_message or "停止超时，已回收桥接进程及其 SDK 子进程。接收端将按超时规则复位。"
        self.process = self.job = self.reader = None
        self.pending = deque(maxlen=1000)
        self.lock = threading.Lock()
        self.stop_deadline = None
        self.forced = False

    @property
    def active(self):
        return self.process is not None

    def start(self, argv):
        if self.active:
            raise RuntimeError("程序正在运行，请先停止。")
        self.pending.clear()
        self.stop_deadline = None
        self.forced = False
        # A USB device must detach before its worker exits. Killing its Job on
        # GUI exit skips finally; stdin EOF instead requests graceful cleanup.
        self.job = WindowsJob() if os.name == "nt" and not self.graceful_only else None
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        try:
            self.process = subprocess.Popen(worker_command(self.module, argv),
                                            cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if self.job:
                self.job.assign(self.process)
            self.reader = threading.Thread(target=self._read, args=(self.process.stdout,), daemon=True)
            self.reader.start()
            self.process.stdin.write("start\n")
            self.process.stdin.flush()
        except Exception:
            if self.graceful_only and self.process:
                # Even a failed start handshake might have delivered "start".
                # EOF lets a Key worker finish detach; never kill it here.
                self.process.stdin.close()
                try:
                    self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    raise RuntimeError("Key 启动异常，后台仍在清理；请保持窗口打开，勿强制结束进程。")
                if self.reader and self.reader.ident is not None:
                    self.reader.join(1)
                self.process.stdout.close()
                self.process = None
                raise
            if self.job:
                self.job.close()
            if self.process:
                if self.process.poll() is None:
                    self.process.kill()
                self.process.wait(timeout=2)
                if self.reader:
                    self.reader.join(1)
                for stream in (self.process.stdin, self.process.stdout):
                    stream.close()
                self.process = None
            raise

    def _read(self, stream):
        try:
            for line in stream:
                line = line.rstrip("\r\n")
                event = {"type": "log", "message": line}
                if line.startswith(EVENT_PREFIX):
                    try:
                        value = json.loads(line[len(EVENT_PREFIX):])
                        if isinstance(value, dict):
                            event = {"type": "status", **value}
                    except ValueError:
                        pass
                with self.lock:
                    self.pending.append(event)
        except (OSError, ValueError):
            pass

    def stop(self, timeout=6.):
        if not self.active or self.stop_deadline is not None:
            return
        self.stop_deadline = time.monotonic() + timeout
        try:
            self.process.stdin.write("stop\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def poll(self):
        result = []
        if self.active and self.stop_deadline is not None and time.monotonic() >= self.stop_deadline and self.process.poll() is None:
            if self.graceful_only:
                self.stop_deadline = float("inf")
                result.append({"type": "status", "phase": "cleanup_wait", "message": self.timeout_message})
            else:
                self.forced = True
                if self.job:
                    self.job.close()
                else:
                    self.process.kill()
                self.stop_deadline = None
                result.append({"type": "log", "message": self.timeout_message})
        with self.lock:
            result.extend(self.pending)
            self.pending.clear()
        if self.active and self.process.poll() is not None:
            if self.job:
                self.job.close()  # Close any orphan native worker, including after a parent crash.
            self.reader.join(.01)
            if not self.reader.is_alive():
                with self.lock:
                    result.extend(self.pending)
                    self.pending.clear()
                code = self.process.returncode
                self.process.stdin.close()
                self.process.stdout.close()
                self.process = self.job = None
                result.append({"type": "exit", "code": code, "forced": self.forced})
        return result


def powershell_command(argv):
    tokens = worker_command("aglass_vrc.cli", argv) if getattr(sys, "frozen", False) else [python_executable(), str(ROOT / "aglass2vrc.py"), *argv]
    return "& " + " ".join("'" + token.replace("'", "''") + "'" for token in tokens)
