"""usbip-win2 0.9.8.1 adapter; loopback server and scoped CLI attachment."""
import importlib.util
import os
from pathlib import Path
import re
import socket
import subprocess
import threading
import time
import uuid

from .usbkey_lifecycle import Journal, KeyGuard, RecoveryRequired


def executable(selected=""):
    path = Path(selected) if selected else Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "USBip" / "usbip.exe"
    return path.resolve() if path.is_file() else None


def choose_backend(selected="auto", client=""):
    if selected not in ("auto", "wdm", "win2"):
        raise ValueError("未知 USB Key 驱动后端")
    return ("win2" if client or executable() else "wdm") if selected == "auto" else selected


def parse_ports(output):
    devices = []
    for block in re.split(r"(?m)(?=^Port \d+:)", output):
        port = re.match(r"Port (\d+):", block)
        if not port:
            continue
        endpoint = re.search(r"-> usbip://([^\s]+)", block)
        if not endpoint or not 1 <= int(port[1]) <= 255:
            raise RuntimeError("无法识别 usbip-win2 端口信息；拒绝猜测设备所有权。")
        devices.append({"port": int(port[1]), "endpoint": endpoint[1]})
    if output.strip() and not devices:
        raise RuntimeError("无法识别 usbip-win2 端口列表。")
    return devices


class Client:
    def __init__(self, selected=""):
        self.path = executable(selected)
        if self.path is None:
            raise OSError("未找到 usbip-win2 客户端；请安装官方 0.9.8.1 或指定 usbip.exe。")
        self.version = self.command("--version").strip()
        if self.version != "0.9.8.1":
            raise RuntimeError(f"此适配器验证的 usbip-win2 版本为 0.9.8.1，当前为 {self.version}")

    def command(self, *args, timeout=20):
        # No shell, no attach retry, no --all. Timeout kills only a CLI helper;
        # ownership reconciliation happens before the server is shut down.
        result = subprocess.run([str(self.path), *map(str, args)], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise RuntimeError(f"usbip-win2 {args[0]} 失败（{result.returncode}）：{result.stderr.strip() or result.stdout.strip()}")
        return result.stdout

    def ports(self):
        return parse_ports(self.command("port"))

    def attach(self, tcp_port, busid):
        output = self.command("--tcp-port", tcp_port, "attach", "--remote", "127.0.0.1",
                              "--bus-id", busid, "--once", "--terse").strip()
        if not output.isascii() or not output.isdigit() or not 1 <= int(output) <= 255:
            raise RuntimeError("无法识别 attach 返回的端口；将按本次唯一连接地址检查清理。")
        return int(output)

    def detach_owned(self, endpoint):
        for item in self.ports():
            if item["endpoint"] == endpoint:
                self.command("detach", "--port", item["port"])
        deadline = time.monotonic() + 5
        while any(item["endpoint"] == endpoint for item in self.ports()):
            if time.monotonic() >= deadline:
                raise RecoveryRequired("usbip-win2 尚未确认移除本次 Key，恢复记录已保留。")
            time.sleep(.1)


class LocalServer:
    """One exclusively bound loopback socket; close every accepted connection."""
    def __init__(self):
        self.sock = None
        self.connections = set()
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.thread = None

    def serve(self, device):
        from usbip import protocol
        device.busnum, device.devnum = 1, 2
        sock = socket.socket()
        self.sock = sock
        try:
            if os.name == "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(("127.0.0.1", 0))
            sock.listen(4)
            sock.settimeout(.2)
            self.port = sock.getsockname()[1]
        except BaseException:
            sock.close()
            raise

        def connection(conn):
            try:
                protocol.serve_connection(conn, [device])
            finally:
                conn.close()
                with self.lock:
                    self.connections.discard(conn)

        def accept():
            while not self.stopping.is_set():
                try:
                    conn, _ = sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with self.lock:
                    if self.stopping.is_set():
                        conn.close()
                        break
                    self.connections.add(conn)
                threading.Thread(target=connection, args=(conn,), daemon=True).start()
        self.thread = threading.Thread(target=accept, daemon=True)
        self.thread.start()

    def stop(self, device=None):
        self.stopping.set()
        if self.sock:
            self.sock.close()
        with self.lock:
            for conn in self.connections:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                conn.close()
        if self.thread:
            self.thread.join(1)


def probe(selected=""):
    client = Client(selected)
    devices = client.ports()
    # Capacity can be configured in the registry; do not claim a fixed value
    # or confuse connected ports with the WDM status table.
    return {"backend": "win2", "version": client.version, "path": str(client.path),
            "capacity": None, "used": [item["port"] for item in devices],
            "dependency": importlib.util.find_spec("usbip") is not None}


def run_device(args, stop, emit, device, key):
    client = Client(args.usbip)
    journal = Journal(backend="win2")
    with KeyGuard():
        previous = journal.read()
        if previous:
            if previous.get("backend") != "win2" or not re.fullmatch(r"127\.0\.0\.1:\d+/aglass-[0-9a-f]{16}", previous.get("endpoint", "")):
                raise RecoveryRequired("usbip-win2 恢复记录不完整，拒绝猜测要拔除的设备。")
            client.detach_owned(previous["endpoint"])
            journal.clear()
        server = LocalServer()
        device.set_busid("aglass-" + uuid.uuid4().hex[:16])
        try:
            device.plug(via=server)
            endpoint = f"127.0.0.1:{server.port}/{device.busid}"
            # Persist ownership before attach, including when the CLI times out.
            journal.write(backend="win2", endpoint=endpoint)
            try:
                if stop.is_set():
                    return 0
                port = client.attach(server.port, device.busid)
                devices = client.ports()
                if not any(d["port"] == port and d["endpoint"] == endpoint for d in devices):
                    raise RuntimeError("usbip-win2 未确认本次 Key 的连接归属。")
                started = time.monotonic()
                last_status = 0
                while not stop.is_set():
                    now = time.monotonic()
                    if now - last_status >= 1:
                        if not any(d["port"] == port and d["endpoint"] == endpoint for d in client.ports()):
                            raise RuntimeError("usbip-win2 的本次 Key 已断开，请检查驱动状态。")
                        last_status = now
                        emit({"phase": "attached", "backend": "win2", "port": port,
                              "medium": args.medium, "commands": key.commands, "completed": key.completed})
                    if args.duration and time.monotonic() - started >= args.duration:
                        break
                    stop.wait(.2)
            finally:
                emit({"phase": "detaching"})
                client.detach_owned(endpoint)
                journal.clear()
                emit({"phase": "detached", "retained": False, "commands": key.commands, "completed": key.completed})
        finally:
            device.unplug()
            server.stop()
    return 0
