#!/usr/bin/env python3
"""动态模块监控: 目标进程里"新加载的 DLL"自动挂钩(不依赖一次性 IAT 扫描)。

机制
----
1) `ntdll!LdrRegisterDllNotification` 注册加载/卸载通知(事件驱动, 官方 API)。
   回调运行在**加载器锁**之下, 所以回调只把事件塞进队列后立刻返回;
2) 后台线程消费队列, 对**白名单内**的模块做 IAT 挂钩(调用 soft_dongle.patch_iat);
3) 另有周期性兜底扫描(默认 5 秒), 覆盖"安装前就已存在"或通知漏掉的模块。

安全约束(实测教训, 别改)
------------------------
* 默认白名单只有 `aGlass_vr_api.dll`。**绝不默认全量挂钩**:
  钩了 `aGlassRuntime.exe` 之后运行时的"模组保活"判定会失败,
  表现为托盘 Eye Mode 菜单过一会儿变灰(厂商字符串"左眼设备断开, 无模组可用")。
* 想全量必须显式给 `'*'`, 并自行承担后果。

用法
----
    import module_watch
    module_watch.start(allow=('aGlass_vr_api.dll',), interval=5.0)
或交给软件狗自动启动: soft_dongle.install(..., watch_modules=('aGlass_vr_api.dll',))
"""
import ctypes
import ctypes.wintypes as w
import fnmatch
import queue
import threading
import time

try:                      # 作为包的一部分被导入时(aglass_vrc/module_watch.py)
    from . import soft_dongle as SD
except ImportError:       # 作为顶层脚本/模块被导入时
    import soft_dongle as SD

# ------------------------------------------------------------------ 通知结构
class _UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort),
                ("Buffer", ctypes.c_void_p)]


class _LDR_LOADED(ctypes.Structure):
    """LDR_DLL_LOADED_NOTIFICATION_DATA: 注意 FullDllName/BaseDllName 是 *指针*"""
    _fields_ = [("Flags", w.DWORD), ("FullDllName", ctypes.c_void_p),
                ("BaseDllName", ctypes.c_void_p), ("DllBase", ctypes.c_void_p),
                ("SizeOfImage", w.DWORD)]


class _LDR_UNLOADED(ctypes.Structure):
    _fields_ = [("Flags", w.DWORD), ("FullDllName", ctypes.c_void_p),
                ("BaseDllName", ctypes.c_void_p), ("DllBase", ctypes.c_void_p)]


def _us_string(ptr):
    if not ptr:
        return ""
    try:
        us = ctypes.cast(ptr, ctypes.POINTER(_UNICODE_STRING)).contents
        if not us.Buffer or not us.Length:
            return ""
        return ctypes.wstring_at(us.Buffer, us.Length // 2)
    except Exception:
        return ""


_queue = queue.Queue()
_cb = None
_state = {"cookie": None, "thread": None, "stop": None, "allow": (), "interval": 5.0}


def _on_notify(reason, data, context):
    """LDR 回调: 必须极快返回(持有加载器锁), 因此只入队。"""
    try:
        if reason == 1 and data:
            d = ctypes.cast(data, ctypes.POINTER(_LDR_LOADED)).contents
            _queue.put(("load", _us_string(d.BaseDllName), int(d.DllBase or 0)))
        elif reason == 2 and data:
            d = ctypes.cast(data, ctypes.POINTER(_LDR_UNLOADED)).contents
            _queue.put(("unload", _us_string(d.BaseDllName), int(d.DllBase or 0)))
    except Exception:
        pass


# ------------------------------------------------------------------ 挂钩逻辑
def _match(name):
    """白名单匹配: 支持 fnmatch 风格(如 `watchtest_*.dll`), 大小写不敏感。"""
    low = (name or "").lower()
    if not low:
        return False
    for pat in _state["allow"]:
        p = (pat or "").lower()
        if not p:
            continue
        if p == "*" or p == low or fnmatch.fnmatchcase(low, p):
            return True
    return False


def _patch_by_name(name, base):
    if not name or not base or not _match(name):
        return False
    if base in SD.S.patched_bases:
        return False
    tables = SD.S.tables
    if not tables:
        return False
    n1 = SD.patch_iat(base, "setupapi", tables[0], log_patched=False)
    n2 = SD.patch_iat(base, "kernel32", tables[1], log_patched=False)
    SD.S.patched_bases.add(base)
    if n1 or n2:
        SD.log("动态挂钩 %s (setupapi %d 项, kernel32 %d 项)" % (name, n1, n2))
    return bool(n1 or n2)


def _sweep():
    """兜底扫描: 找出白名单里尚未挂钩的模块。"""
    try:
        for name, path, base, size in SD.self_modules():
            if not base or name.lower() in ("kernel32.dll", "ntdll.dll", "kernelbase.dll"):
                continue
            _patch_by_name(name, base)
    except Exception as e:
        SD.log("兜底扫描异常: %r" % (e,))


def _worker():
    interval = _state["interval"]
    while not _state["stop"].is_set():
        got = None
        try:
            got = _queue.get(timeout=interval)
        except queue.Empty:
            got = None
        if got:
            if got[0] == "unload":
                SD.S.patched_bases.discard(got[2])
            else:
                _patch_by_name(got[1], got[2])
        _sweep()
    SD.log("动态模块监控已停止")


def start(allow=("aGlass_vr_api.dll",), interval=5.0):
    """注册 DLL 加载通知并启动消费线程。可重复调用(第二次为空操作)。"""
    global _cb
    if _state["thread"] is not None and _state["thread"].is_alive():
        return True
    _state["allow"] = tuple(a for a in (allow or ()) if a)
    _state["interval"] = max(0.5, float(interval))
    _state["stop"] = threading.Event()

    status = None
    try:
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.LdrRegisterDllNotification.argtypes = [w.DWORD, ctypes.c_void_p, ctypes.c_void_p,
                                                     ctypes.POINTER(ctypes.c_void_p)]
        ntdll.LdrRegisterDllNotification.restype = ctypes.c_long
        _cb = ctypes.WINFUNCTYPE(None, w.DWORD, ctypes.c_void_p, ctypes.c_void_p)(_on_notify)
        cookie = ctypes.c_void_p(0)
        status = ntdll.LdrRegisterDllNotification(0, ctypes.cast(_cb, ctypes.c_void_p), None,
                                                  ctypes.byref(cookie))
        _state["cookie"] = cookie
    except Exception as e:
        status = -1
        SD.log("LdrRegisterDllNotification 失败: %r" % (e,))

    thread = threading.Thread(target=_worker, name="soft-dongle-modwatch", daemon=True)
    thread.start()
    _state["thread"] = thread
    SD.log("动态模块监控: 白名单=%s, 兜底扫描 %.1fs, 通知注册=%s" % (
        ",".join(_state["allow"]) or "-", _state["interval"],
        "OK" if status == 0 else "失败(仅靠扫描)"))
    _sweep()
    return True


def stop():
    if _state["stop"] is not None:
        _state["stop"].set()
