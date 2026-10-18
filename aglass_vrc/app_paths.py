"""Writable portable application directory versus bundled Python resources."""
from pathlib import Path
import sys


def application_root():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


def worker_command(module, argv):
    if getattr(sys, "frozen", False):
        mode = {"aglass_vrc.gui_runner": "--bridge", "aglass_vrc.usbkey_runner": "--key",
                "aglass_vrc.cli": "--cli"}.get(module)
        if mode is None:
            raise ValueError(f"Unsupported bundled worker: {module}")
        worker = application_root() / "aGlass2OSC-worker.exe"
        if not worker.is_file():
            raise OSError("缺少 aGlass2OSC-worker.exe，请完整解压发布包，勿只复制 GUI EXE。")
        return [str(worker), mode, *argv]
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return [str(executable), "-u", "-m", module, *argv]
