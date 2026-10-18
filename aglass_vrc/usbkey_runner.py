"""GUI-owned virtual USB Key worker, also usable from the command line."""
import argparse
import json
import logging
from pathlib import Path
import threading
import time

from .gui_runner import EVENT_PREFIX, control_commands
from .usbkey_device import ReadOnlyImage, RecordedKey, TRACE, make_device
from .usbkey_lifecycle import Journal, cooperative_signals

LOG = logging.getLogger(__name__)


def run(args, stop, emit):
    from .vhci import Controller, forward, probe
    from . import usbip_win2
    backend = usbip_win2.choose_backend(args.backend, args.usbip)
    if args.probe:
        emit({"phase": "probe", **(usbip_win2.probe(args.usbip) if backend == "win2" else {"backend": "wdm", **probe()})})
        return 0
    # Validate files and dependencies before attaching anything to Windows.
    image = ReadOnlyImage(args.image, args.medium)
    key = RecordedKey(args.key)
    try:
        from usbip.core import SPEED_HIGH
    except ImportError as exc:
        raise RuntimeError("缺少 USB Key 可选依赖，请运行：python -m pip install -r requirements-usbkey.txt") from exc
    device = make_device(image, key, args.medium)
    device.set_speed(SPEED_HIGH)  # This WDM VHCI expects high-speed bulk endpoints.
    if backend == "win2":
        return usbip_win2.run_device(args, stop, emit, device, key)
    journal = Journal()
    started = time.monotonic()
    last_status = 0
    controller = None

    def heartbeat(force=False):
        nonlocal last_status
        now = time.monotonic()
        if args.duration and now - started >= args.duration:
            stop.set()
        if controller and controller.port is not None and (force or now - last_status >= 1):
            last_status = now
            emit({"phase": "attached", "port": controller.port, "medium": args.medium,
                  "commands": key.commands, "completed": key.completed})

    try:
        controller = Controller(stop, heartbeat)
        controller.acquire_guard()
        ports = controller.ports()
        journal.check_wdm(controller.path, ports["used"])
        if ports["capacity"] is not None and len(ports["used"]) >= ports["capacity"]:
            raise RuntimeError("WDM 驱动端口已满，拒绝再次接入；请恢复控制器或改用 usbip-win2。")
        if stop.is_set():
            return 0
        journal.write(backend="wdm", path=controller.path, baseline=ports["used"])
        controller.attach(device)
        journal.write(backend="wdm", path=controller.path, port=controller.port)
        LOG.info("USB Key attached: port=%s medium=%s read-only=%d bytes", controller.port, args.medium, len(image.data))
        heartbeat(True)
        forward(controller, device, stop, heartbeat)
    except InterruptedError:
        if not stop.is_set():
            raise
    finally:
        if controller:
            controller.heartbeat = None
            port = controller.port
            try:
                emit({"phase": "detaching"})
                controller.close(release_guard=False)
                if port is not None:
                    # WDM includes detached PDOs until PnP removal completes.
                    retained = None
                    deadline = time.monotonic() + 3
                    try:
                        while True:
                            retained = port in probe()["used"]
                            if not retained or time.monotonic() >= deadline:
                                break
                            time.sleep(.1)
                    except OSError as exc:
                        LOG.warning("Key 已关闭；无法复查驱动端口状态：%s", exc)
                    if retained is False:
                        journal.clear()
                    else:
                        LOG.warning("端口 %d 未确认释放，已保留恢复记录；下次启动将先检查，拒绝继续消耗槽位。", port)
                    emit({"phase": "detached", "commands": key.commands, "completed": key.completed, "retained": retained})
            finally:
                controller.release_guard()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--backend", choices=("auto", "wdm", "win2"), default="auto")
    parser.add_argument("--usbip", default="", help="usbip-win2 0.9.8.1 usbip.exe; omit for installed location")
    parser.add_argument("--key", type=Path, default=TRACE, help="command trace JSON or AGLASSKEY1 BIN")
    parser.add_argument("--image", type=Path, help="read-only block image; omit for blank media")
    parser.add_argument("--medium", choices=("cdrom", "disk"), default="cdrom")
    parser.add_argument("--duration", type=float, default=0)
    args = parser.parse_args(argv)
    if not 0 <= args.duration < float("inf"):
        parser.error("duration must be finite and nonnegative")
    stop = threading.Event()
    if args.gui:
        commands = control_commands()
        if next(commands, None) != "start":
            return 2

        def control():
            try:
                for line in commands:
                    if line == "stop":
                        break
            finally:
                stop.set()

        threading.Thread(target=control, name="USB Key stop", daemon=True).start()

    def emit(event):
        try:
            print(EVENT_PREFIX + json.dumps(event, ensure_ascii=True), flush=True)
        except (BrokenPipeError, OSError):
            stop.set()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    try:
        with cooperative_signals(stop):
            return run(args, stop, emit)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        emit({"phase": "error", "message": str(exc)})
        LOG.error("USB Key: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
