"""Private GUI subprocess entry: structured status on stdout, stop over stdin."""
import json
import logging
import os
import sys
import threading
import time

from .cli import parse_args, run

EVENT_PREFIX = "@AGLASS_GUI "


def control_commands():
    """Do not leave a blocking read pending on inherited Windows standard input.

    A pending synchronous pipe read can stall initialization of an SDK child.
    PeekNamedPipe lets the control thread read only bytes already available.
    https://learn.microsoft.com/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe
    """
    fd = sys.stdin.fileno()
    if os.name == "nt":
        import ctypes as C
        from ctypes import wintypes as W
        import msvcrt
        api = C.WinDLL("kernel32", use_last_error=True)
        api.PeekNamedPipe.argtypes = [W.HANDLE, C.c_void_p, W.DWORD, C.c_void_p, C.POINTER(W.DWORD), C.c_void_p]
        api.PeekNamedPipe.restype = W.BOOL
        handle, available = msvcrt.get_osfhandle(fd), W.DWORD()
    pending = b""
    while True:
        count = 128
        if os.name == "nt":
            if not api.PeekNamedPipe(handle, None, 0, None, C.byref(available), None):
                if C.get_last_error() in (109, 232):  # broken pipe / no data after closure
                    return
                raise C.WinError(C.get_last_error())
            if not available.value:
                time.sleep(.02)
                continue
            count = min(count, available.value)
        data = os.read(fd, count)
        if not data:
            return
        pending += data
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            yield line.strip().decode("ascii", errors="replace")
        if len(pending) > 128:
            return


def main():
    # Do not load a native SDK or create children until the GUI owns our job.
    commands = control_commands()
    if next(commands, None) != "start":
        return 2
    stop = threading.Event()

    def read_control():
        try:
            for line in commands:
                if line == "stop":
                    break
        finally:
            stop.set()  # Also stop if the GUI closes its end of the pipe.

    def emit(event):
        try:
            print(EVENT_PREFIX + json.dumps(event, ensure_ascii=True, allow_nan=False), flush=True)
        except (BrokenPipeError, OSError):
            stop.set()

    threading.Thread(target=read_control, name="GUI stop control", daemon=True).start()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    try:
        return run(parse_args(), stop_event=stop, observer=emit)
    except (InterruptedError, KeyboardInterrupt):
        if stop.is_set():
            return 0
        raise
    except Exception as exc:
        emit({"phase": "error", "message": str(exc)})
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
