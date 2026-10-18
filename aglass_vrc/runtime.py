"""Read-only discovery of the user's running aGlass Runtime and adjacent SDK.

No process is launched, stopped, or assigned to the bridge's Windows Job.
"""
import ctypes as C
from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class RunningRuntime:
    pid: int
    executable: Path


def find_running_runtimes():
    if os.name != "nt":
        raise RuntimeError("检测已运行的 aGlass Runtime 需要 Windows。")
    from ctypes import wintypes as W

    # https://learn.microsoft.com/windows/win32/api/tlhelp32/ns-tlhelp32-processentry32w
    class ProcessEntry(C.Structure):
        _fields_ = [("size", W.DWORD), ("usage", W.DWORD), ("pid", W.DWORD),
                    ("heap", C.c_size_t), ("module", W.DWORD), ("threads", W.DWORD),
                    ("parent", W.DWORD), ("priority", W.LONG), ("flags", W.DWORD),
                    ("name", W.WCHAR * 260)]

    api = C.WinDLL("kernel32", use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes, api.CreateToolhelp32Snapshot.restype = [W.DWORD, W.DWORD], W.HANDLE
    for name in ("Process32FirstW", "Process32NextW"):
        getattr(api, name).argtypes = [W.HANDLE, C.POINTER(ProcessEntry)]
        getattr(api, name).restype = W.BOOL
    api.OpenProcess.argtypes, api.OpenProcess.restype = [W.DWORD, W.BOOL, W.DWORD], W.HANDLE
    api.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
    api.QueryFullProcessImageNameW.restype = W.BOOL
    api.CloseHandle.argtypes, api.CloseHandle.restype = [W.HANDLE], W.BOOL

    snapshot = api.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    result = []
    try:
        entry = ProcessEntry()
        entry.size = C.sizeof(entry)
        available = api.Process32FirstW(snapshot, C.byref(entry))
        while available:
            if entry.name.casefold() == "aglassruntime.exe":
                # Query permission only; never request termination or VM access.
                handle = api.OpenProcess(0x1000, False, entry.pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                if not handle:
                    code = C.get_last_error()
                    raise RuntimeError(f"无法读取 Runtime PID {entry.pid} 的路径（Windows 错误 {code}）；请刷新检测或取消复用后手动选择 DLL。")
                try:
                    buffer = C.create_unicode_buffer(32768)
                    length = W.DWORD(len(buffer))
                    if not api.QueryFullProcessImageNameW(handle, 0, buffer, C.byref(length)):
                        code = C.get_last_error()
                        raise RuntimeError(f"无法读取 Runtime PID {entry.pid} 的路径（Windows 错误 {code}）；请刷新检测。")
                    result.append(RunningRuntime(entry.pid, Path(buffer.value)))
                finally:
                    api.CloseHandle(handle)
            available = api.Process32NextW(snapshot, C.byref(entry))
        if C.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise C.WinError(C.get_last_error())
    finally:
        api.CloseHandle(snapshot)
    return result


def running_runtime_sdk(sdk="auto"):
    """Resolve only within the single running Runtime's installation directory."""
    names = {"auto": ("aGlass_vr_api.dll", "aGlassClient.dll"),
             "legacy": ("aGlass_vr_api.dll",), "client": ("aGlassClient.dll",)}[sdk]
    processes = find_running_runtimes()
    if not processes:
        raise RuntimeError("未检测到已运行的 aGlassRuntime.exe。请先启动配套 Runtime，或取消“使用已运行的 Runtime”后手动选择 DLL。")
    if len(processes) != 1:
        detail = "; ".join(f"PID {p.pid}: {p.executable}" for p in processes)
        raise RuntimeError(f"检测到多个 aGlass Runtime，无法自动确定连接对象。请保留一个 Runtime 后重试。{detail}")
    runtime = processes[0]
    base = runtime.executable.parent
    # Do not call dll_candidates: that also searches the repository and other installs.
    for name in names:
        for folder in (base, base / "Client and Plugins/Client", base / "bin", base / "bin/Client and Plugins/Client"):
            path = folder / name
            if path.is_file():
                return runtime, path.resolve()
    raise RuntimeError(f"已找到 Runtime PID {runtime.pid}，但其目录 {base} 内没有所选接口的配套 DLL（{' / '.join(names)}）。请选择匹配的设备 / Runtime 接口，或取消复用后手动选择 DLL。")
