"""Crash records and cooperative shutdown shared by USB Key backends."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal


class RecoveryRequired(RuntimeError):
    pass


class Journal:
    def __init__(self, path=None, backend="wdm"):
        self.path = Path(path) if path else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "aGlass2OSC" / f"usbkey-{backend}-state.json"

    def read(self):
        if not self.path.exists():
            return None
        try:
            value = json.loads(self.path.read_text("utf-8"))
            if not isinstance(value, dict) or value.get("backend") not in ("wdm", "win2"):
                raise ValueError("invalid recovery record")
            return value
        except (ValueError, OSError) as exc:
            raise RecoveryRequired(f"无法读取 USB Key 恢复记录 {self.path}：{exc}") from exc

    def write(self, **value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)

    def clear(self):
        self.path.unlink(missing_ok=True)

    def check_wdm(self, path, used):
        previous = self.read()
        if previous and previous["backend"] == "wdm" and previous.get("path") == path:
            port = previous.get("port")
            remaining = ({port} & set(used) if port is not None
                         else set(used) - set(previous.get("baseline", [])))
            if remaining:
                raise RecoveryRequired("上次 Key 尚未确认移除，拒绝继续占用新端口。请恢复 WDM 控制器或重启 Windows，再检测驱动。")
        # Do not overwrite an unresolved record from the other backend.
        if previous and previous["backend"] != "wdm":
            raise RecoveryRequired("usbip-win2 存在未完成清理的记录，请先用该后端检查并恢复。")


@contextmanager
def cooperative_signals(stop):
    """Ctrl+C requests detach; a second Ctrl+C must not interrupt its finally."""
    previous = {}
    try:
        for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            sig = getattr(signal, name, None)
            if sig is not None:
                previous[sig] = signal.signal(sig, lambda *_: stop.set())
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


class KeyGuard:
    def __enter__(self):
        import ctypes as C
        from .vhci import NativeAPI
        self.api = NativeAPI()
        self.handle = self.api.k.CreateMutexW(None, False, "Local\\aGlass2OSC.VirtualUSBKey")
        error = C.get_last_error()
        if not self.handle:
            raise C.WinError(error)
        if error == 183:
            self.__exit__()
            raise RuntimeError("另一个 aGlass2OSC 已启动虚拟 Key，请直接使用现有设备。")
        return self

    def __exit__(self, *exc):
        if self.handle:
            self.api.k.CloseHandle(self.handle)
            self.handle = None
