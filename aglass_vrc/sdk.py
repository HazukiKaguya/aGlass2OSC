"""Separate ctypes bindings for legacy and Client APIs. No hardware access on import."""
from __future__ import annotations

import ctypes as C
from dataclasses import dataclass
import hashlib
import logging
import math
import os
from pathlib import Path
import socket
import struct
import threading
import time

LOG = logging.getLogger(__name__)
CALLBACK = getattr(C, "WINFUNCTYPE", C.CFUNCTYPE)
KNOWN_ZERO_SUCCESS_DLLS = {"fec75b232d7ba0bca66eb59ea532240333b4d30b6413015ada9f7ee9a05b9659"}
KNOWN_ONE_SUCCESS_DLLS = {"1628c890191d0de2ee7087c4d55d9d779b0df54b2d67f5a8ed9db0a79ad0cc23"}
# SDK exports alone do not distinguish these two incompatible data-item enums.
CLIENT_SCHEMAS = {
    "timestamped": (1, 2, 3, 4, 5),  # timestamp, gazeX, gazeY, gazeVaild, eyeValid
    "no-timestamp": (None, 1, 2, 3, 4),
}
KNOWN_CLIENT_SCHEMAS = {
    "bace1829ae9cb49250238c6603ec7133c93230dffccf1f2fcc4165f463f28368": "timestamped",
    "3220b01de503414628d2e8ecaa514abbf3d959c689ebe37dc75e562c3dd01c1c": "timestamped",
    "df696485cf7dcad7ff3ffa4df47bfedee7ae68dcc36fbdcb4a69d3a5ce8b6796": "timestamped",
    "baffb5c9c14eace4fe1fa923a225bef6cad0316f0888cdc1e121f12c26f4bd95": "no-timestamp",
}
KNOWN_SINGLE_EYE_BUG_DLLS = {
    "3220b01de503414628d2e8ecaa514abbf3d959c689ebe37dc75e562c3dd01c1c",
    "baffb5c9c14eace4fe1fa923a225bef6cad0316f0888cdc1e121f12c26f4bd95",
}
PROFILES = {
    "auto": ("auto", None, "Inspect DLL exports; recognize the bundled legacy DLL"),
    "bundled": ("legacy", 0, "Runtime 1.1.0.0 legacy callbacks (repository or matching installed DLL)"),
    "vi1-legacy": ("legacy", 1, "DK I = vi-1, original documented SDK"),
    "vi1-1.1": ("client", 0, "DK I = vi-1, upgraded Client API"),
    "dkii": ("client", 0, "DK II, Client API"),
}


class Point(C.Structure):
    _fields_ = [("x", C.c_float), ("y", C.c_float)]


class GazeData(C.Structure):
    _fields_ = [("timestamp", C.c_int64), ("valid", C.c_int), ("gazePoint", Point),
                ("pupilRadius", C.c_float), ("pupilCenter", Point), ("exData", C.c_float * 16)]


class Calibration(C.Structure):
    _fields_ = [("coe", C.c_ubyte * 1024)]


class LegacyInit(C.Structure):
    _fields_ = [("calibCoe", Calibration), ("pathSize", C.c_int), ("path", C.c_wchar_p)]


class ClientInit(C.Structure):
    _fields_ = [("devEventPort", C.c_int), ("eyeDataPort", C.c_int)]


LegacyCallback = CALLBACK(None, C.POINTER(GazeData))
ClientCallback = CALLBACK(None, C.c_void_p, C.c_void_p)
EventCallback = CALLBACK(None, C.c_int, C.c_void_p)


@dataclass(frozen=True)
class Sample:
    timestamp: int
    received: float
    valid: bool
    x: float
    y: float
    eye_valid: bool | None = None


class Samples:
    """Copy each callback before returning; never retain a native SDK data pointer."""
    def __init__(self):
        self.lock = threading.Lock()
        self.data: dict[str, Sample] = {}
        self.error: str | None = None

    def put(self, eye, timestamp, valid, x, y, eye_valid=None, now=None):
        sample = Sample(timestamp, time.monotonic() if now is None else now,
                        bool(valid) and math.isfinite(x) and math.isfinite(y), x, y, eye_valid)
        with self.lock:
            old = self.data.get(eye)
            if old and timestamp != 0 and old.timestamp == timestamp:
                return  # Repeated frames must not refresh the freshness timer.
            self.data[eye] = sample

    def snapshot(self):
        with self.lock:
            if self.error:
                raise RuntimeError(self.error)
            return dict(self.data)

    def fail(self, exc):
        with self.lock:
            self.error = f"SDK callback failed: {exc}"

    def clear(self):
        with self.lock:
            self.data.clear()


def bind(lib, name, args, result=C.c_int):
    fn = getattr(lib, name)
    fn.argtypes, fn.restype = args, result


def detect_sdk(lib):
    if all(hasattr(lib, n) for n in ("aGlass_start_device", "aGlass_start_eye_callback", "aGlass_get_eye_data_float")):
        return "client"
    if all(hasattr(lib, n) for n in ("aGlass_start", "aGlass_get_mode", "aGlass_start_tracking")):
        return "legacy"
    raise RuntimeError("Unrecognized aGlass DLL exports. Select a DLL matching your Runtime.")


def dll_candidates(root, sdk):
    names = ["aGlass_vr_api.dll", "aGlassClient.dll"] if sdk == "auto" else [
        "aGlass_vr_api.dll" if sdk == "legacy" else "aGlassClient.dll"]
    bases = [root, root.parent] if root.name == "release" else [root]
    bases += [Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "aGlass"]
    result = []
    for name in names:
        for base in bases:
            for folder in (base / "bin", base, base / "bin/Client and Plugins/Client", base / "Client and Plugins/Client"):
                path = folder / name
                if path.is_file() and path not in result:
                    result.append(path)
        for base in bases:
            # Also list user-extracted SDKs / demos; installed and bundled DLLs retain priority.
            if (base / "res").is_dir():
                for path in sorted((base / "res").rglob(name)):
                    if path not in result:
                        result.append(path)
    return result


def client_schema(path, requested="auto"):
    if requested != "auto":
        if requested not in CLIENT_SCHEMAS:
            raise ValueError(f"Unknown Client schema: {requested}")
        return requested
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest in KNOWN_SINGLE_EYE_BUG_DLLS:
        LOG.warning("This vendor DLL has unreliable gaze validity in single-eye Runtime modes. "
                    "Dual-eye mode passed the offline test; use a matching updated Client for single-eye tracking. "
                    "Use the Client DLL that matches your Runtime/SDK version; see README.md.")
    if digest in KNOWN_CLIENT_SCHEMAS:
        return KNOWN_CLIENT_SCHEMAS[digest]
    LOG.warning("Unknown Client DLL: assuming timestamped data-item IDs. The early DK II Demo uses "
                "--client-schema no-timestamp; confirm with the matching SDK before overriding.")
    return "timestamped"


def success_code(path, profile, override=None):
    if override is not None:
        return override
    configured = PROFILES[profile][1]
    if configured is not None:
        return configured
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest in KNOWN_ZERO_SUCCESS_DLLS:
        return 0
    if digest in KNOWN_ONE_SUCCESS_DLLS:
        return 1
    LOG.warning("Unknown legacy DLL: using documented success=1. Confirm its API documentation; "
                "--legacy-success-code can select 0 or 1. No automatic retry with opposite semantics.")
    return 1


def load_sdk(path):
    if os.name != "nt" or C.sizeof(C.c_void_p) != 8:
        raise RuntimeError("aGlass requires Windows and 64-bit Python. Simulation needs no hardware.")
    path = Path(path).resolve()
    with path.open("rb") as f:
        if f.read(2) != b"MZ":
            raise RuntimeError(f"Not a Windows DLL: {path}")
        f.seek(60)
        offset = struct.unpack("<I", f.read(4))[0]
        f.seek(offset)
        if f.read(4) != b"PE\0\0" or f.read(2) != b"\x64\x86":
            raise RuntimeError("Select the x64 aGlass DLL; x86 DLLs cannot be used with this bridge.")
    try:
        directory = os.add_dll_directory(str(path.parent))
        try:
            lib = C.WinDLL(str(path))
        except Exception:
            directory.close()
            raise
        return lib, directory
    except OSError as exc:
        raise RuntimeError(f"Cannot load {path}: {exc}. Check x64 VC++ runtime and adjacent DLL dependencies.") from exc


def legacy_parameters(host="127.0.0.1", send_port=2000, recv_port=2001, timeout=5.):
    """Vendor demo protocol: 1024-byte UDP requests, UTF-16 path then coefficients."""
    remote = socket.gethostbyname(host)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        receiver.bind(("127.0.0.1", recv_port))

        def request(command):
            sender.sendto(command.ljust(1024, b"\0"), (remote, send_port))
            deadline = time.monotonic() + timeout
            while True:
                receiver.settimeout(max(.001, deadline - time.monotonic()))
                try:
                    payload, source = receiver.recvfrom(4096)
                except socket.timeout as exc:
                    raise RuntimeError("UDP handshake timed out. Start the matching aGlass Runtime and check its UDP ports; "
                                       "for a Client DLL use --profile vi1-1.1 / dkii.") from exc
                if source[0] == remote:
                    return payload
                if time.monotonic() >= deadline:
                    raise RuntimeError("No response from the configured aGlass Runtime.")

        raw_path = request(b"path")
        if not raw_path or len(raw_path) > 1024 or len(raw_path) % 2:
            raise RuntimeError("Invalid Runtime path packet (expected UTF-16LE, at most 1024 bytes).")
        path = raw_path.decode("utf-16-le").split("\0", 1)[0]
        if not path or len(path.encode("utf-16-le")) > 1022:
            raise RuntimeError("Runtime returned an empty or oversized calibration path.")
        # Use the Runtime response, not Guest.dat bytes. Real hardware tests with
        # the same DLL/path produced right-only mode from the file, both eyes
        # from this response (see docs/HARDWARE_VALIDATION.md).
        coeff = request(b"request")
        if len(coeff) != 1024:
            raise RuntimeError(f"Invalid calibration packet: {len(coeff)} bytes; expected 1024.")
        # pathSize is buffer capacity; retain the 512-wchar buffer through SDK release.
        buffer = C.create_unicode_buffer(path, 512)
        params = LegacyInit()
        params.pathSize, params.path = 512, C.cast(buffer, C.c_wchar_p)
        C.memmove(C.addressof(params.calibCoe), coeff, 1024)
        return params, buffer


ERRORS = {
    -1: "operation failed", -2: "Runtime did not respond", -3: "invalid parameter",
    -101: "USB authorization key not found", -102: "USB key mismatch", -103: "USB key password error",
    -104: "USB key expired", -105: "USB key unauthorized", -106: "no device or multiple devices",
    -107: "configuration could not be read", -108: "base calibration data could not be read",
    -109: "unsupported USB key", 1001: "invalid parameter", 1002: "left eye device not found",
    1003: "right eye device not found", 2001: "USB authorization key not found",
    2002: "USB key connection failed", 2003: "USB key login failed", 2004: "USB key verification failed",
    2005: "USB key expired", 2006: "USB key permission denied", 2007: "USB key access failed",
}


class Backend:
    def __init__(self, lib, samples, success):
        self.lib, self.samples, self.success = lib, samples, success
        self.cleanup = []

    def check(self, name, *args):
        result = getattr(self.lib, name)(*args)
        if result != self.success:
            detail = ERRORS.get(result, "unexpected return value / SDK profile mismatch")
            raise RuntimeError(f"{name} returned {result} ({detail}); expected {self.success}. "
                               "Check --profile and the Runtime/DLL pairing.")

    def step(self, name, undo, *args):
        self.check(name, *args)
        self.cleanup.append(undo)

    def close(self):
        while self.cleanup:
            try:
                self.check(self.cleanup.pop())
            except Exception as exc:
                LOG.warning("Cleanup: %s", exc)


class LegacyBackend(Backend):
    def __init__(self, lib, samples, success=1):
        super().__init__(lib, samples, success)
        bind(lib, "aGlass_init", [C.POINTER(LegacyInit)])
        for name in ("aGlass_release", "aGlass_start", "aGlass_stop", "aGlass_stop_tracking"):
            bind(lib, name, [])
        bind(lib, "aGlass_get_mode", [C.POINTER(C.c_int)])
        bind(lib, "aGlass_start_tracking", [LegacyCallback, LegacyCallback])
        self.callbacks = [LegacyCallback(self.callback(eye)) for eye in ("left", "right")]

    def callback(self, eye):
        def receive(ptr):
            try:
                if ptr:
                    d = ptr.contents
                    self.samples.put(eye, d.timestamp, d.valid == 1, d.gazePoint.x, d.gazePoint.y)
            except Exception as exc:
                self.samples.fail(exc)
        return receive

    def start(self, args):
        self.params, self.path_buffer = legacy_parameters(args.runtime_host, args.runtime_send_port,
                                                        args.runtime_recv_port, args.timeout)
        self.step("aGlass_init", "aGlass_release", C.byref(self.params))
        mode = C.c_int(-1)
        self.check("aGlass_get_mode", C.byref(mode))
        if mode.value not in (0, 1, 2):
            raise RuntimeError(f"Unsupported aGlass device mode {mode.value}")
        self.active_eyes = ("left",) if mode.value == 0 else ("right",) if mode.value == 1 else ("left", "right")
        LOG.info("SDK eye mode: %s", ", ".join(self.active_eyes))
        self.step("aGlass_start", "aGlass_stop")
        self.step("aGlass_start_tracking", "aGlass_stop_tracking", *self.callbacks)


class ClientBackend(Backend):
    """Public Client getters expose one merged gaze; do not reinterpret opaque memory."""
    active_eyes = ("center",)

    def __init__(self, lib, samples, schema="timestamped"):
        super().__init__(lib, samples, 0)
        self.schema = schema
        self.items = CLIENT_SCHEMAS[schema]
        bind(lib, "aGlass_init", [C.POINTER(ClientInit)])
        for name in ("aGlass_release", "aGlass_stop_device", "aGlass_stop_eye_callback", "aGlass_start_tracking", "aGlass_stop_tracking"):
            bind(lib, name, [])
        bind(lib, "aGlass_start_device", [EventCallback, C.c_void_p])
        bind(lib, "aGlass_start_eye_callback", [ClientCallback, C.c_void_p])
        bind(lib, "aGlass_get_eye_data_int", [C.c_void_p, C.c_int, C.POINTER(C.c_int)])
        bind(lib, "aGlass_get_eye_data_float", [C.c_void_p, C.c_int, C.POINTER(C.c_float)])
        bind(lib, "aGlass_get_eye_data_byte", [C.c_void_p, C.c_int, C.POINTER(C.c_ubyte), C.c_int])
        self.eye_callback = ClientCallback(self.receive)
        self.event_callback = EventCallback(self.event)

    def event(self, code, _user):
        # Follow the header enum: the 1.1 PDF's protocol table reverses these labels.
        if code in (0, 2):
            self.samples.clear()
        LOG.info("aGlass device event: %s", {0: "left disconnected", 1: "left connected",
                                           2: "right disconnected", 3: "right connected"}.get(code, code))

    def receive(self, ptr, _user):
        try:
            if not ptr:
                return
            stamp_id, x_id, y_id, valid_id, eye_id = self.items
            valid, eye_valid = C.c_int(-12345), C.c_int(-12345)
            x, y = C.c_float(float("nan")), C.c_float(float("nan"))
            self.check("aGlass_get_eye_data_int", ptr, valid_id, C.byref(valid))
            self.check("aGlass_get_eye_data_int", ptr, eye_id, C.byref(eye_valid))
            if valid.value not in (0, 1) or eye_valid.value not in (0, 1):
                raise RuntimeError(f"Client validity getter did not return a boolean "
                                   f"(gaze={valid.value}, eye={eye_valid.value}); check --client-schema and matching DLL.")
            timestamp = 0  # Early Demo has no timestamp; freshness uses actual callback arrivals.
            if stamp_id is not None:
                stamp = (C.c_ubyte * 8)(*[0xA5] * 8)
                self.check("aGlass_get_eye_data_byte", ptr, stamp_id, stamp, 8)
                if bytes(stamp) == b"\xa5" * 8:
                    raise RuntimeError("Client timestamp getter wrote no data; check --client-schema no-timestamp.")
                timestamp = int.from_bytes(stamp, "little", signed=True)
            if valid.value == 1:
                self.check("aGlass_get_eye_data_float", ptr, x_id, C.byref(x))
                self.check("aGlass_get_eye_data_float", ptr, y_id, C.byref(y))
            self.samples.put("center", timestamp,
                             valid.value == 1 and eye_valid.value == 1, x.value, y.value, eye_valid.value == 1)
        except Exception as exc:
            self.samples.fail(exc)

    def start(self, args):
        self.params = ClientInit(args.event_port, args.data_port)
        self.step("aGlass_init", "aGlass_release", C.byref(self.params))
        self.step("aGlass_start_device", "aGlass_stop_device", self.event_callback, None)
        self.step("aGlass_start_eye_callback", "aGlass_stop_eye_callback", self.eye_callback, None)
        self.step("aGlass_start_tracking", "aGlass_stop_tracking")
