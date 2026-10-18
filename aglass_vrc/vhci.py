"""Owned, cancellable USB transport for cezanne/usbip-win's WDM VHCI.

ABI layout was supplied in aglass-usbip-dongle-v1.0/vhci_attach.py. This
adapter uses the project's USB device model and never unplugs all ports.
No driver installation, elevation, TCP listener or vendor DLL is involved.
"""
import ctypes as C
import importlib.util
import os
import struct
import threading
import time
import uuid

GUID = "d35f7840-6a0c-11d2-b841-00c04fad5171"
PLUGIN, UNPLUG, PORTS = 0x2A4000, 0x2A4004, 0x2A400C
PLUG_SIZE, DEV_OFFSET, CONFIG_OFFSET = 296, 266, 284
SERIAL = "AGLASS2OSC01"
MAX_TRANSFER = 1024 * 1024
USB_HUB_QUERY = 0x220408  # ROOT_HUB_NAME on a controller, NODE_INFORMATION on a hub.


def hub_port_count(raw):
    # USB_NODE_INFORMATION: NodeType (ULONG), packed USB_HUB_DESCRIPTOR.
    if (len(raw) < 76 or raw[:4] != bytes(4) or raw[4] < 9 or raw[5] != 0x29
            or not 1 <= raw[6] <= 127):
        raise OSError("invalid USB root hub descriptor")
    return raw[6]


def port_status(raw, capacity=None):
    if not raw or not 1 <= raw[0] <= 127 or len(raw) < 1 + raw[0]:
        raise OSError("unexpected VHCI port status; incompatible driver")
    # WDM hardcodes n_max_ports=127 here although its actual hub has six ports.
    return {"capacity": capacity, "table_size": raw[0],
            "used": [i for i in range(raw[0]) if raw[i + 1]]}


class NoFreePortError(RuntimeError):
    pass


def plugin_request(device_descriptor, config_descriptor, serial=SERIAL):
    """Validate the variable-length driver request before crossing into kernel."""
    if len(device_descriptor) != 18 or device_descriptor[:2] != b"\x12\x01":
        raise ValueError("invalid USB device descriptor")
    if (not 9 <= len(config_descriptor) <= 65535 or config_descriptor[:2] != b"\x09\x02"
            or int.from_bytes(config_descriptor[2:4], "little") != len(config_descriptor)):
        raise ValueError("invalid USB configuration descriptor")
    encoded = serial.encode("utf-16-le")
    if not encoded or len(encoded) > 254 or "\0" in serial:
        raise ValueError("invalid VHCI serial")
    size = PLUG_SIZE - 9 + len(config_descriptor)
    result = bytearray(size)
    struct.pack_into("<II", result, 0, size, 0x10001)
    result[10:10 + len(encoded)] = encoded
    result[DEV_OFFSET:DEV_OFFSET + 18] = device_descriptor
    result[CONFIG_OFFSET:CONFIG_OFFSET + len(config_descriptor)] = config_descriptor
    return bytes(result)


def parse_request(header):
    """Only control/bulk USB/IP requests; VHCI uses little-endian PDUs."""
    if len(header) != 48:
        raise ValueError("short VHCI request")
    cmd, seq, devid, direction, ep, flags, length, _frame, packets, interval = struct.unpack_from("<IIIIIIiiii", header)
    if cmd not in (1, 2):
        raise ValueError("unknown VHCI command")
    if cmd == 1 and (direction not in (0, 1) or ep > 15 or not 0 <= length <= MAX_TRANSFER or packets > 0):
        raise ValueError("invalid or unsupported VHCI transfer")
    return cmd, seq, devid, direction, ep, flags, length, interval, header[40:48]


def completion(urb):
    if not 0 <= urb.actual <= urb.length or (urb.direction == 1 and urb.actual > len(urb.buffer)):
        raise ValueError("invalid USB completion length")
    header = struct.pack("<IIIIIiiiii8x", 3, urb.seqnum, 0, 0, 0, urb.status, urb.actual, 0, 0, 0)
    return header + (urb.buffer[:urb.actual] if urb.direction == 1 else b"")


class NativeAPI:
    def __init__(self):
        if os.name != "nt":
            raise OSError("VHCI direct attachment requires Windows")
        from ctypes import wintypes as W
        self.W = W
        self.k = C.WinDLL("kernel32", use_last_error=True)
        self.s = C.WinDLL("setupapi", use_last_error=True)

        class Interface(C.Structure):
            _fields_ = [("size", W.DWORD), ("guid", C.c_byte * 16), ("flags", W.DWORD), ("reserved", C.c_void_p)]

        class Overlapped(C.Structure):
            _fields_ = [("internal", C.c_size_t), ("internal_high", C.c_size_t),
                        ("offset", W.DWORD), ("offset_high", W.DWORD), ("event", W.HANDLE)]

        self.Interface, self.Overlapped = Interface, Overlapped
        specs = {
            "CreateFileW": (W.HANDLE, [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]),
            "CloseHandle": (W.BOOL, [W.HANDLE]),
            "CreateEventW": (W.HANDLE, [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]),
            "CreateMutexW": (W.HANDLE, [C.c_void_p, W.BOOL, W.LPCWSTR]),
            "WaitForSingleObject": (W.DWORD, [W.HANDLE, W.DWORD]),
            "CancelIoEx": (W.BOOL, [W.HANDLE, C.POINTER(Overlapped)]),
            "GetOverlappedResult": (W.BOOL, [W.HANDLE, C.POINTER(Overlapped), C.POINTER(W.DWORD), W.BOOL]),
            "ReadFile": (W.BOOL, [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(Overlapped)]),
            "WriteFile": (W.BOOL, [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(Overlapped)]),
            "DeviceIoControl": (W.BOOL, [W.HANDLE, W.DWORD, C.c_void_p, W.DWORD, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(Overlapped)]),
        }
        for name, (restype, argtypes) in specs.items():
            function = getattr(self.k, name)
            function.restype, function.argtypes = restype, argtypes
        specs = {
            "SetupDiGetClassDevsW": (W.HANDLE, [C.c_void_p, W.LPCWSTR, W.HWND, W.DWORD]),
            "SetupDiEnumDeviceInterfaces": (W.BOOL, [W.HANDLE, C.c_void_p, C.c_void_p, W.DWORD, C.POINTER(Interface)]),
            "SetupDiGetDeviceInterfaceDetailW": (W.BOOL, [W.HANDLE, C.POINTER(Interface), C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p]),
            "SetupDiDestroyDeviceInfoList": (W.BOOL, [W.HANDLE]),
        }
        for name, (restype, argtypes) in specs.items():
            function = getattr(self.s, name)
            function.restype, function.argtypes = restype, argtypes

    def path(self):
        guid = C.create_string_buffer(uuid.UUID(GUID).bytes_le, 16)
        info = self.s.SetupDiGetClassDevsW(guid, None, None, 0x12)
        if info in (None, C.c_void_p(-1).value):
            raise C.WinError(C.get_last_error())
        try:
            index = 0
            while True:
                item = self.Interface()
                item.size = C.sizeof(item)
                if not self.s.SetupDiEnumDeviceInterfaces(info, None, guid, index, C.byref(item)):
                    if C.get_last_error() == 259:
                        return None
                    raise C.WinError(C.get_last_error())
                index += 1
                size = self.W.DWORD()
                self.s.SetupDiGetDeviceInterfaceDetailW(info, C.byref(item), None, 0, C.byref(size), None)
                if not 6 <= size.value <= 65536:
                    raise OSError("invalid VHCI interface path size")
                buffer = C.create_string_buffer(size.value)
                C.cast(buffer, C.POINTER(self.W.DWORD))[0] = 8 if C.sizeof(C.c_void_p) == 8 else 6
                if not self.s.SetupDiGetDeviceInterfaceDetailW(info, C.byref(item), buffer, size, None, None):
                    raise C.WinError(C.get_last_error())
                path = C.wstring_at(C.addressof(buffer) + 4)
                if path.lower().startswith("\\\\?\\usbipwin#vhci#"):
                    return path
        finally:
            self.s.SetupDiDestroyDeviceInfoList(info)


class Controller:
    def __init__(self, stop=None, heartbeat=None):
        self.api = NativeAPI()
        self.stop = stop or threading.Event()
        self.heartbeat = heartbeat
        self.port = None
        self.guard = None
        self.path = self.api.path()
        if not self.path:
            raise OSError("未找到 cezanne/usbip-win WDM VHCI；请先安装兼容驱动。")
        self.handle = self.api.k.CreateFileW(self.path, 0xC0000000, 0, None, 3, 0x40000000, None)
        if self.handle in (None, C.c_void_p(-1).value):
            self.handle = None
            raise C.WinError(C.get_last_error())

    def _io(self, action, timeout=None, stopping=True, handle=None):
        api = self.api
        handle = self.handle if handle is None else handle
        event = api.k.CreateEventW(None, True, False, None)
        if not event:
            raise C.WinError(C.get_last_error())
        ov = api.Overlapped()
        ov.event = event
        count = api.W.DWORD()
        pending = False
        try:
            if not action(C.byref(count), C.byref(ov)):
                if C.get_last_error() != 997:  # ERROR_IO_PENDING
                    raise C.WinError(C.get_last_error())
                pending = True
                deadline = time.monotonic() + timeout if timeout else None
                while True:
                    wait = api.k.WaitForSingleObject(event, 50)
                    if wait == 0:
                        break
                    if wait != 258:
                        raise C.WinError(C.get_last_error())
                    if stopping and self.stop.is_set():
                        raise InterruptedError("VHCI stopped")
                    if deadline and time.monotonic() >= deadline:
                        raise TimeoutError("VHCI I/O timed out")
                    if self.heartbeat:
                        self.heartbeat()
                pending = False
                if not api.k.GetOverlappedResult(handle, C.byref(ov), C.byref(count), False):
                    raise C.WinError(C.get_last_error())
            return count.value
        finally:
            if pending:
                # Keep OVERLAPPED and buffers alive until the cancelled IRP completes.
                api.k.CancelIoEx(handle, C.byref(ov))
                api.k.GetOverlappedResult(handle, C.byref(ov), C.byref(count), True)
            api.k.CloseHandle(event)

    def ioctl(self, code, payload=b"", size=0, stopping=True, handle=None):
        handle = self.handle if handle is None else handle
        incoming = C.create_string_buffer(payload)
        outgoing = C.create_string_buffer(max(size, 1))
        count = self._io(lambda n, ov: self.api.k.DeviceIoControl(handle, code, incoming, len(payload), outgoing, size, n, ov),
                         timeout=2, stopping=stopping, handle=handle)
        return outgoing.raw[:count]

    def ports(self):
        raw = self.ioctl(PORTS, size=128)
        result = port_status(raw)
        try:
            result["capacity"] = self.hub_capacity()
        except OSError as exc:
            result["capacity_error"] = str(exc)
        return result

    def hub_capacity(self):
        raw = self.ioctl(USB_HUB_QUERY, size=4096)
        if len(raw) < 6 or not 6 <= int.from_bytes(raw[:4], "little") <= len(raw):
            raise OSError("invalid USB root hub name response")
        name = raw[4:len(raw) & ~1].decode("utf-16-le").split("\0", 1)[0]
        if (not name.lower().startswith(("usbipwin#", "usb#root_hub")) or "\\" in name
                or not name.lower().endswith("#{f18a0e88-c30c-11d0-8815-00a0c906bed8}")):
            raise OSError("unexpected USB/IP root hub path")
        hub = self.api.k.CreateFileW("\\\\?\\" + name, 0xC0000000, 3, None, 3, 0x40000000, None)
        if hub in (None, C.c_void_p(-1).value):
            raise C.WinError(C.get_last_error())
        try:
            return hub_port_count(self.ioctl(USB_HUB_QUERY, bytes(76), 76, handle=hub))
        finally:
            self.api.k.CloseHandle(hub)

    def acquire_guard(self):
        if self.guard is None:
            self.guard = self.api.k.CreateMutexW(None, False, "Local\\aGlass2OSC.VirtualUSBKey")
            error = C.get_last_error()
            if not self.guard:
                raise C.WinError(error)
            if error == 183:
                self.api.k.CloseHandle(self.guard)
                self.guard = None
                raise RuntimeError("另一个 aGlass2OSC 已启动虚拟 Key，请直接使用现有设备。")

    def attach(self, device):
        if self.port is not None:
            raise RuntimeError("this handle already owns a device")
        request = plugin_request(device.device_descriptor().pack(), device.config_bytes())
        self.acquire_guard()
        try:
            raw = self.ioctl(PLUGIN, request, PLUG_SIZE)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 38:
                raise NoFreePortError("VHCI 没有可分配的端口（WinError 38）；已拔除设备的残留记录可能占满实际端口。"
                                      "请先停止虚拟 USB/IP 设备，再恢复虚拟控制器。该错误发生在设备接入阶段，与 Key 文件内容无关。") from exc
            raise
        # WDM uses zero-based ports 0..126; negative values are global commands.
        if len(raw) < 9 or not 0 <= raw[8] < 127:
            raise OSError("VHCI returned an invalid port")
        self.port = raw[8]
        return self.port

    def read(self, size):
        data = bytearray()
        while len(data) < size:
            buffer = C.create_string_buffer(size - len(data))
            count = self._io(lambda n, ov: self.api.k.ReadFile(self.handle, buffer, len(buffer), n, ov))
            if not count:
                raise OSError("VHCI device disconnected")
            data.extend(buffer.raw[:count])
        return bytes(data)

    def write(self, data):
        while data:
            buffer = C.create_string_buffer(data, len(data))
            count = self._io(lambda n, ov: self.api.k.WriteFile(self.handle, buffer, len(buffer), n, ov), timeout=2)
            if not count:
                raise OSError("VHCI wrote zero bytes")
            data = data[count:]

    def release_guard(self):
        if self.guard:
            self.api.k.CloseHandle(self.guard)
            self.guard = None

    def close(self, release_guard=True):
        if self.handle is None:
            return
        try:
            if self.port is not None:
                self.ioctl(UNPLUG, struct.pack("<b3x", self.port), stopping=False)
        finally:
            self.api.k.CloseHandle(self.handle)
            self.handle = self.port = None
            if release_guard:
                self.release_guard()


def probe():
    """Open/query/close only: creates no USB device and takes no other port."""
    controller = Controller()
    try:
        return {"path": controller.path, **controller.ports(),
                "dependency": importlib.util.find_spec("usbip") is not None}
    finally:
        controller.close()


def forward(controller, device, stop, heartbeat=lambda: None):
    from usbip.core import Urb
    lock = threading.Lock()
    count = 0

    def respond(urb):
        with lock:
            controller.write(completion(urb))

    device.reset_io()
    try:
        while not stop.is_set():
            cmd, seq, devid, direction, ep, flags, length, interval, setup = parse_request(controller.read(48))
            if cmd == 2:
                device.cancel_urb(flags)
                controller.write(struct.pack("<IIIIIiiiii8x", 4, seq, 0, 0, 0, 0, 0, 0, 0, 0))
                continue
            data = controller.read(length) if direction == 0 and length else b""
            urb = Urb(cmd, seq, devid, direction, ep, flags, length, interval, setup, data)
            if device.handle_urb(urb, respond) is not None:
                respond(urb)
            count += 1
            heartbeat()
    finally:
        device.reset_io()
    return count
