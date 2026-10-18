"""Pure Python client for the verified aGlass Runtime 1.1 TCP/UDP protocol.

The installed 1.1 stream differs from its PDF. See docs/RUNTIME_DIRECT.md.
No vendor DLL, injection, or SDK subprocess is used by this backend.
"""
import logging
import select
import socket
import struct
import time
import zlib

from .runtime import find_running_runtimes

LOG = logging.getLogger(__name__)
CRC_SEED = 0xf8e7f8e7


def runtime_endpoint(port=0):
    if port:
        return "127.0.0.1", port
    processes = find_running_runtimes()
    if not processes:
        raise RuntimeError("未检测到 aGlassRuntime.exe；请先启动 Runtime，再使用直连模式。")
    if len(processes) != 1:
        raise RuntimeError("检测到多个 Runtime，请保留一个实例，或明确指定 Runtime TCP 端口。")
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\aGlassRuntime\Service") as key:
            value = winreg.QueryValueEx(key, "ListenPort")[0]
        port = int(str(value).split("\0", 1)[0].strip())
        if not 1 <= port <= 65535:
            raise ValueError("port out of range")
    except (OSError, ValueError) as exc:
        raise RuntimeError("无法读取 Runtime 的 ListenPort，请在高级设置中填写 Runtime TCP 端口。") from exc
    runtime = processes[0]
    LOG.info("直连现有 Runtime | PID %s | %s | TCP %s", runtime.pid, runtime.executable, port)
    return "127.0.0.1", port


def decode_gaze(packet, mode):
    """Return one eye, timestamp, gaze validity, x, y, and pupil validity.

    In the verified 1.1 Client receiver, gaze=1 selects left, gaze=2 selects
    right; BOTH use packet offsets 172/176. Invalid prefixes -1/-2 clear the
    respective eye. These are eye identifiers, not a 0/1 Boolean or bit mask.
    """
    if len(packet) != 1024:
        raise ValueError("眼动 UDP 包长度不是 1024")
    prefix, stamp, pupil = struct.unpack_from("<iqi", packet)
    gaze, x, y = struct.unpack_from("<iff", packet, 168)
    if stamp <= 0 or pupil not in (0, 1, 2, 4) or gaze not in (0, 1, 2):
        raise ValueError("眼动 UDP 字段与 Runtime 1.1 格式不符")
    eye_id = gaze or {-1: 1, -2: 2}.get(prefix)
    if eye_id is None:
        eye_id = mode if mode in (1, 2) else None
    if eye_id is None or (mode in (1, 2) and eye_id != mode):
        raise ValueError("无法确定数据所属眼睛，或眼别与跟踪模式不符")
    eye_valid = pupil in (eye_id, 4)
    return ("left" if eye_id == 1 else "right", stamp, bool(gaze) and eye_valid, x, y, eye_valid)


class RuntimeBackend:
    def __init__(self, samples):
        self.samples = samples
        self.tcp = self.data = self.events = None
        self.cleanup = []
        self.active_eyes = ()
        self.mode = None
        self.stop_event = None
        self.timeout, self.stop_timeout = 5., 3.
        self.synchronized = True
        self.last_stamps = {}
        self.received = self.rejected = 0

    def connect(self, args, stop_event=None):
        self.stop_event = stop_event
        self.timeout, self.stop_timeout = args.timeout, args.sdk_stop_timeout
        self._cancelled()
        address = runtime_endpoint(args.runtime_port)
        self.tcp = socket.create_connection(address, timeout=self.timeout)
        self.tcp.setblocking(False)
        self._cancelled()
        LOG.info("Runtime TCP 已连接 %s:%s；不加载厂商 DLL，不创建 SDK 子进程。", *address)

    def _cancelled(self):
        if self.stop_event is not None and self.stop_event.is_set():
            raise InterruptedError("Runtime 直连启动已取消。")

    def _wait(self, writing, deadline, cancellable):
        while True:
            if cancellable:
                self._cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Runtime 控制命令响应超时。")
            read, write, _ = select.select([] if writing else [self.tcp], [self.tcp] if writing else [], [], min(.05, remaining))
            if read or write:
                return

    def command(self, code, payload=b"", timeout=None, cancellable=True):
        packet = bytearray(4096)
        struct.pack_into("<iii", packet, 0, code, len(payload), 0)
        packet[12:12 + len(payload)] = payload
        struct.pack_into("<I", packet, 4092, zlib.crc32(packet[:4092], CRC_SEED))
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        self.synchronized = False
        sent = 0
        while sent < len(packet):
            self._wait(True, deadline, cancellable)
            count = self.tcp.send(packet[sent:])
            if not count:
                raise ConnectionError("Runtime 控制连接已关闭。")
            sent += count
        response = bytearray()
        while len(response) < 4096:
            self._wait(False, deadline, cancellable)
            part = self.tcp.recv(4096 - len(response))
            if not part:
                raise ConnectionError("Runtime 控制连接已关闭。")
            response.extend(part)
        returned, size, _unused_extra = struct.unpack_from("<iii", response)
        crc = struct.unpack_from("<I", response, 4092)[0]
        minimum = 16 if code == 7001 else 4
        if returned != code or not minimum <= size <= 4080 or crc != zlib.crc32(response[:4092], CRC_SEED):
            raise RuntimeError("Runtime 控制响应的命令、长度或 CRC 不正确；请确认使用受支持的 Runtime 1.1。")
        # extraLen is unused and actually uninitialized in the installed Runtime.
        self.synchronized = True
        result = struct.unpack_from("<i", response, 12)[0]
        if result != 0:
            raise RuntimeError(f"Runtime 命令 {code} 返回 {result}，请检查 Runtime 的设备及授权状态。")
        return bytes(response[12:12 + size])

    def start(self, args, stop_event=None):
        self.connect(args, stop_event)
        for attr, port in (("events", args.event_port), ("data", args.data_port)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            setattr(self, attr, sock)
            sock.bind(("127.0.0.1", port))
            sock.setblocking(False)
        response = self.command(7001, struct.pack("<ii", args.event_port, args.data_port))
        self.cleanup.append(7002)
        self.mode = struct.unpack_from("<i", response, 4)[0]
        if self.mode not in (1, 2, 3):
            raise RuntimeError(f"未知 Runtime 跟踪模式 {self.mode}。")
        self.active_eyes = {1: ("left",), 2: ("right",), 3: ("left", "right")}[self.mode]
        # Installed bace... Client sends no 7005/7006. The real 1.1 Runtime
        # returned an invalid response to 7005; follow the verified sequence.
        for start, stop in ((7003, 7004), (7007, 7008)):
            self.command(start)
            self.cleanup.append(stop)
        LOG.info("Runtime 直连已开始 | 眼睛：%s | UDP %s / %s", ", ".join(self.active_eyes), args.event_port, args.data_port)

    def poll(self):
        if select.select([self.tcp], [], [], 0)[0]:
            if not self.tcp.recv(1, socket.MSG_PEEK):
                raise ConnectionError("Runtime 已关闭控制连接，停止眼动输出。")
            raise RuntimeError("Runtime 发送了非预期控制消息，停止当前会话。")
        for sock in (self.events, self.data):
            for _ in range(256):
                try:
                    packet, source = sock.recvfrom(2048)
                except BlockingIOError:
                    break
                if source[0] != "127.0.0.1":
                    continue
                if sock is self.events:
                    if len(packet) == 1024:
                        code, event = struct.unpack_from("<ii", packet)
                        if code == 8000 and event in (0, 2):
                            self.samples.clear()
                            self.last_stamps.clear()
                    continue
                try:
                    eye, stamp, valid, x, y, pupil = decode_gaze(packet, self.mode)
                except ValueError as exc:
                    self.rejected += 1
                    if self.rejected == 1:
                        LOG.warning("忽略无法解析的 Runtime 数据包：%s", exc)
                    continue
                self.received += 1
                if stamp <= self.last_stamps.get(eye, 0):
                    continue
                self.last_stamps[eye] = stamp
                self.samples.put(eye, stamp, valid, x, y, pupil)

    def close(self):
        deadline = time.monotonic() + self.stop_timeout
        while self.cleanup and self.tcp and self.synchronized and time.monotonic() < deadline:
            code = self.cleanup.pop()
            try:
                self.command(code, timeout=deadline - time.monotonic(), cancellable=False)
            except (OSError, RuntimeError) as exc:
                LOG.warning("Runtime 会话清理：%s", exc)
        self.cleanup.clear()
        for attr in ("events", "data", "tcp"):
            sock = getattr(self, attr)
            if sock is not None:
                sock.close()
                setattr(self, attr, None)
        LOG.info("Runtime 直连已断开 | 收到 %s 包，拒绝 %s 包；未结束 Runtime 进程。", self.received, self.rejected)
