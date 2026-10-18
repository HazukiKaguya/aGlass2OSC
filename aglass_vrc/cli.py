"""Command line entry point. Run python aglass2vrc.py --help."""
import argparse
import csv
import ctypes as C
import logging
import math
from pathlib import Path
import socket
import sys
import time

from .sdk import (CLIENT_SCHEMAS, PROFILES, ClientBackend, LegacyBackend, Samples, client_schema, detect_sdk,
                  dll_candidates, load_sdk, success_code)
from .tracking import BLINK_ADDRESS, EyeOutput, Projection
from .vrcft import VrcftOutput
from .sdk_process import IsolatedBackend
from .runtime import running_runtime_sdk
from .runtime_client import RuntimeBackend

LOG = logging.getLogger(__name__)
from .app_paths import application_root

ROOT = application_root()


def parser():
    p = argparse.ArgumentParser(description="aGlass DK I (vi-1) / DK II -> VRChat / VRCFaceTracking")
    p.add_argument("--target", choices=("native", "vrcft-avatar", "vrcft-module"), default="native",
                   help="native VRChat OSC, direct v2 float avatar parameters, or the separately installed VRCFT module")
    p.add_argument("--parameter-prefix", default="v2", help="Direct avatar eye parameter prefix, e.g. FT/v2")
    p.add_argument("--profile", choices=PROFILES, default="auto", help="Runtime/SDK compatibility profile (default: auto)")
    p.add_argument("--connection", choices=("sdk", "runtime"), default="sdk",
                   help="sdk: vendor DLL; runtime: direct Runtime 1.1 TCP/UDP without vendor DLL or SDK child process")
    p.add_argument("--runtime-port", type=int, default=0, help="Direct Runtime TCP port; 0 reads the running Runtime's registry port")
    p.add_argument("--list-profiles", action="store_true")
    p.add_argument("--list-dlls", action="store_true", help="List candidate DLL paths; no initialization")
    p.add_argument("--dll", type=Path, help="DLL from the installed matching Runtime/SDK")
    p.add_argument("--use-running-runtime", action="store_true",
                   help="Use the SDK beside the single running aGlassRuntime.exe; do not start or stop Runtime")
    p.add_argument("--soft-dongle", action="store_true",
                   help="Fake the USB authorization key inside this process (no key hardware, no administrator rights)")
    p.add_argument("--legacy-success-code", type=int, choices=(0, 1), help="Explicit legacy ABI return convention override")
    p.add_argument("--client-schema", choices=("auto", *CLIENT_SCHEMAS), default="auto",
                   help="Client data-item IDs: auto recognizes SDK/Demo DLL hashes; early DK II Demo has no timestamp")
    p.add_argument("--diagnose", action="store_true", help="SDK mode: inspect DLL ABI; direct mode: check TCP connection only. No device initialization or OSC")
    p.add_argument("--sdk-isolation", choices=("process", "in-process"), default="process",
                   help="Default: keep native SDK crashes in a child process; in-process is for debugging")
    p.add_argument("--sdk-start-timeout", type=float, default=30., help="Maximum seconds to start an isolated SDK")
    p.add_argument("--sdk-stop-timeout", type=float, default=3., help="Maximum seconds for isolated native cleanup")
    p.add_argument("--host", default="127.0.0.1", help="OSC destination (module accepts loopback only)")
    p.add_argument("--port", type=int, help="Default: 9000 for VRChat, 9015 for the VRCFT module")
    p.add_argument("--rate", type=float, default=60., help="OSC frames per second")
    p.add_argument("--projection", choices=("auto", "steamvr", "fov"), default="auto",
                   help="auto: use available SteamVR projection, otherwise desktop FOV; fov never connects to SteamVR")
    p.add_argument("--fov-x", type=float, default=100., help="Full horizontal FOV for approximate mode")
    p.add_argument("--fov-y", type=float, default=100., help="Full vertical FOV for approximate mode")
    p.add_argument("--gaze-space", choices=("viewport", "panel"), default="viewport",
                   help="Panel mode additionally uses SteamVR lens distortion mapping")
    p.add_argument("--center-x", type=float, default=.5)
    p.add_argument("--center-y", type=float, default=.5)
    p.add_argument("--gain-x", type=float, default=1.)
    p.add_argument("--gain-y", type=float, default=1.)
    p.add_argument("--invert-x", action="store_true")
    p.add_argument("--invert-y", action="store_true")
    p.add_argument("--output", choices=("center", "per-eye"), default="center",
                   help="per-eye requires legacy callbacks or direct Runtime 1.1")
    p.add_argument("--smoothing-ms", type=float, default=25., help="Exponential time constant; 0 disables smoothing")
    p.add_argument("--stale-seconds", type=float, default=.25, help="Stop resending gaze after this frame age")
    p.add_argument("--blink", choices=("off", "validity"), default="validity",
                   help="default: validity heuristic; off disables blink estimation")
    p.add_argument("--blink-delay-ms", type=float, default=30.)
    p.add_argument("--blink-max-seconds", type=float, default=.6, help="Longer data loss is not treated as closed eyes")
    p.add_argument("--runtime-host", default="127.0.0.1", help="Legacy Runtime host (normally localhost)")
    p.add_argument("--runtime-send-port", type=int, default=2000)
    p.add_argument("--runtime-recv-port", type=int, default=2001)
    p.add_argument("--timeout", type=float, default=5., help="Legacy handshake timeout")
    p.add_argument("--event-port", type=int, default=2002, help="Local UDP device event port for Client API")
    p.add_argument("--data-port", type=int, default=2003, help="Local UDP eye data port for Client API")
    p.add_argument("--log", type=Path, help="Create a new CSV with raw gaze and outgoing OSC values")
    p.add_argument("--simulate", action="store_true", help="Generate moving gaze without aGlass; can send real OSC")
    p.add_argument("--dry-run", action="store_true", help="Process data but do not create an OSC socket")
    p.add_argument("--duration", type=float, default=0., help="Exit after N seconds; 0 runs until Ctrl+C")
    return p


def parse_args(argv=None):
    p = parser()
    a = p.parse_args(argv)
    if not 0 <= a.runtime_port <= 65535:
        p.error("--runtime-port must be 0 (automatic) or in [1, 65535]")
    if a.connection == "runtime":
        if a.dll or a.use_running_runtime or a.soft_dongle or a.profile != "auto" or a.legacy_success_code is not None or a.client_schema != "auto" or a.list_dlls:
            p.error("Runtime direct mode does not use DLL/profile/soft-dongle options; remove those options")
        if a.runtime_host not in ("127.0.0.1", "localhost"):
            p.error("Runtime direct mode currently supports localhost only")
    if a.use_running_runtime and a.dll:
        p.error("--use-running-runtime selects the SDK automatically; omit --dll")
    if a.use_running_runtime and a.runtime_host not in ("127.0.0.1", "localhost"):
        p.error("--use-running-runtime requires a local Runtime; use --runtime-host 127.0.0.1")
    if a.port is None:
        a.port = 9015 if a.target == "vrcft-module" else 9000
    a.parameter_prefix = a.parameter_prefix.strip("/")
    if not a.parameter_prefix or any(c in a.parameter_prefix for c in " ,#*?[]{}\x00\r\n\t"):
        p.error("--parameter-prefix must be a nonempty OSC path without wildcard characters or spaces")
    for name in ("rate", "fov_x", "fov_y", "gain_x", "gain_y", "stale_seconds", "timeout", "blink_max_seconds",
                 "sdk_start_timeout", "sdk_stop_timeout"):
        value = getattr(a, name)
        if not math.isfinite(value) or value <= 0:
            p.error(f"--{name.replace('_', '-')} must be finite and positive")
    for name in ("smoothing_ms", "blink_delay_ms", "duration"):
        value = getattr(a, name)
        if not math.isfinite(value) or value < 0:
            p.error(f"--{name.replace('_', '-')} must be finite and nonnegative")
    if a.rate > 240 or a.fov_x >= 179 or a.fov_y >= 179:
        p.error("rate must be <= 240 Hz and FOV must be < 179 degrees")
    for name in ("center_x", "center_y"):
        if not math.isfinite(getattr(a, name)) or not 0 <= getattr(a, name) <= 1:
            p.error(f"--{name.replace('_', '-')} must be in [0, 1]")
    for name in ("port", "runtime_send_port", "runtime_recv_port", "event_port", "data_port"):
        if not 1 <= getattr(a, name) <= 65535:
            p.error(f"--{name.replace('_', '-')} must be in [1, 65535]")
    if a.event_port < 1025 or a.data_port < 1025 or a.event_port == a.data_port:
        p.error("Client event/data ports must be distinct and in [1025, 65535]")
    if a.blink_delay_ms / 1000 >= a.blink_max_seconds:
        p.error("blink delay must be shorter than maximum blink duration")
    if a.projection == "fov" and a.gaze_space == "panel":
        p.error("--gaze-space panel requires --projection steamvr")
    return a


class OscSender:
    def __init__(self, host, port):
        try:
            from pythonosc.osc_message_builder import OscMessageBuilder
        except ImportError as exc:
            raise RuntimeError("Install dependencies: python -m pip install -r requirements.txt") from exc
        self.builder = OscMessageBuilder
        self.destination = (socket.gethostbyname(host), port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, address, values):
        message = self.builder(address=address)
        for value in values:
            if isinstance(value, bool):
                message.add_arg(value)  # OSC T/F tags; do not encode status as a float.
            else:
                message.add_arg(float(value), arg_type="f")
        self.socket.sendto(message.build().dgram, self.destination)

    def close(self):
        self.socket.close()


def install_soft_dongle(lib, path):
    """Fake the USB authorization key inside this process; no key hardware, no admin rights.

    The legacy vendor DLL performs the key handshake itself, so patching its own import
    table is enough (aglass_vrc/soft_dongle.py). The Client API keeps the key check inside
    aGlassRuntime.exe, so for those profiles the Runtime must be started with the same hook.
    """
    from . import soft_dongle
    base = soft_dongle.install(dll_handle=lib, hide_real=True, emulate=True,
                               logger=lambda *parts: LOG.info(" ".join(str(part) for part in parts)))
    LOG.info("软件狗已装入本进程 | 模块 %s | 基址 0x%X | 无需 USB Key", Path(path).name, base)
    return base


def make_backend(args, samples):
    requested = PROFILES[args.profile][0]
    if args.use_running_runtime:
        runtime, path = running_runtime_sdk(requested)
        LOG.info("使用已运行的 Runtime | PID: %s | %s | SDK: %s", runtime.pid, runtime.executable, path)
        candidates = [path]
    else:
        candidates = [args.dll] if args.dll else dll_candidates(ROOT, requested)
    if not candidates:
        raise RuntimeError("aGlass DLL not found. Use --dll with the x64 DLL from your Runtime/SDK.")
    path = candidates[0].resolve()
    lib, directory = load_sdk(path)
    try:
        if args.soft_dongle:
            install_soft_dongle(lib, path)
        detected = detect_sdk(lib)
        if requested != "auto" and requested != detected:
            raise RuntimeError(f"Profile {args.profile} requires {requested} API, but {path} exports {detected} API.")
        if args.soft_dongle and detected == "client":
            LOG.warning("Client DLL does not check the USB key itself; that check lives in aGlassRuntime.exe. "
                        "Start the Runtime with the soft dongle loaded for Client profiles.")
        if detected == "client":
            if args.legacy_success_code is not None:
                raise RuntimeError("--legacy-success-code applies only to the legacy API.")
            if args.output == "per-eye":
                raise RuntimeError("Client API exposes combined gaze. Select --output center.")
            schema = client_schema(path, args.client_schema)
            LOG.info("Client data schema: %s", schema)
            backend = ClientBackend(lib, samples, schema)
        else:
            if args.client_schema != "auto":
                raise RuntimeError("--client-schema applies only to the Client API.")
            backend = LegacyBackend(lib, samples, success_code(path, args.profile, args.legacy_success_code))
        LOG.info("DLL: %s | API: %s | success code: %s", path, detected, backend.success)
        return backend, directory
    except Exception:
        directory.close()
        raise


def simulate(samples, elapsed, frame, now):
    valid = elapsed % 4 < 3.8
    x = .5 + .2 * math.sin(elapsed * 1.5)
    y = .5 + .15 * math.sin(elapsed)
    for eye in ("left", "right"):
        samples.put(eye, frame + 1, valid, x, y, now=now)


def run(args, stop_event=None, observer=None):
    samples = Samples()
    backend = directory = projection = sender = log_file = output = None
    def report(**event):
        if observer:
            observer(event)
    try:
        report(phase="diagnosing" if args.diagnose else "starting")
        if args.diagnose or not args.simulate:
            if args.connection == "runtime":
                backend = RuntimeBackend(samples)
            elif args.sdk_isolation == "process":
                backend = IsolatedBackend(samples)
            else:
                backend, directory = make_backend(args, samples)
        if args.diagnose:
            if isinstance(backend, RuntimeBackend):
                backend.connect(args, stop_event)
                LOG.info("Runtime TCP 连接检查通过；未初始化设备或发送 OSC。")
                return 0
            if isinstance(backend, IsolatedBackend):
                backend.start(args, stop_event)
            LOG.info("ABI bindings ready. Python: %s-bit. No device initialization or OSC performed.", C.sizeof(C.c_void_p) * 8)
            return 0
        projection = Projection(args)
        if args.log:
            log_file = args.log.open("x", encoding="utf-8", newline="")
            writer = csv.writer(log_file)
            writer.writerow(["elapsed", "address", "values", "left_x", "left_y", "left_valid",
                             "right_x", "right_y", "right_valid", "center_x", "center_y", "center_valid"])
        if not args.dry_run:
            sender = OscSender(args.host, args.port)
        if backend:
            if isinstance(backend, (IsolatedBackend, RuntimeBackend)):
                backend.start(args, stop_event)
            else:
                backend.start(args)
            active = backend.active_eyes
        else:
            active = ("left", "right")
        output_type = EyeOutput if args.target == "native" else VrcftOutput
        output = output_type(args, projection, active)
        LOG.info("%s -> %s:%s, %s Hz, target=%s, blink=%s. Ctrl+C to stop.",
                 "SIMULATION" if args.simulate else "aGlass", args.host, args.port, args.rate, args.target, args.blink)
        if args.dry_run:
            LOG.info("DRY RUN: no OSC packets are transmitted.")
        if args.blink == "validity":
            LOG.warning("Blink is estimated from validity, not measured eyelid openness; tracking loss can resemble a blink.")
        elif args.target == "vrcft-module":
            LOG.info("Blink off: the module supplies neutral open eyelids; VRCFT controls outgoing eye behavior.")
        started = next_tick = time.monotonic()
        next_status = started
        next_observation = started
        last_messages = {}
        frame = packets = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            now = time.monotonic()
            elapsed = now - started
            if args.duration and elapsed >= args.duration:
                break
            if args.simulate:
                simulate(samples, elapsed, frame, now)
            if isinstance(backend, (IsolatedBackend, RuntimeBackend)):
                backend.poll()
                now = time.monotonic()  # Direct UDP polling timestamps samples in this process.
                elapsed = now - started
            snapshot = samples.snapshot()
            messages = output.messages(snapshot, now)
            for address, values in messages:
                if observer:
                    last_messages[address] = values
                if sender:
                    sender.send(address, values)
                    packets += 1
            if observer and now >= next_observation:
                report(phase="running", elapsed=elapsed, packets=packets, simulate=args.simulate,
                       dry_run=args.dry_run, target=args.target, stale_seconds=args.stale_seconds,
                       samples={eye: {"x": s.x if math.isfinite(s.x) else None,
                                      "y": s.y if math.isfinite(s.y) else None,
                                      "valid": s.valid, "age": max(0., now - s.received)}
                                for eye, s in snapshot.items()}, messages=last_messages.copy())
                next_observation = now + .1
            if log_file:
                raw = []
                for eye in ("left", "right", "center"):
                    s = snapshot.get(eye)
                    raw += [s.x, s.y, s.valid] if s else ["", "", ""]
                for address, values in messages or [("", ())]:
                    writer.writerow([f"{elapsed:.6f}", address, " ".join(f"{v:.7f}" for v in values), *raw])
            if now >= next_status:
                status = ", ".join(f"{e}=({s.x:.3f},{s.y:.3f}) valid={s.valid} age={now - s.received:.3f}s"
                                   for e, s in snapshot.items()) or "waiting for SDK callbacks"
                gaze = next((v for address, v in messages if address != BLINK_ADDRESS), None)
                LOG.info("%s | gaze=%s | UDP packets=%d", status, gaze, packets)
                if log_file:
                    log_file.flush()
                next_status = now + 1.
            frame += 1
            next_tick += 1. / args.rate
            delay = next_tick - time.monotonic()
            if delay > 0:
                if stop_event is not None:
                    stop_event.wait(delay)
                else:
                    time.sleep(delay)
            else:
                next_tick = time.monotonic()  # No catch-up packet burst after a slow frame.
        return 0
    finally:
        # Send the neutral state before entering vendor shutdown. Some Client DLLs
        # can block or raise a native exception while closing a receiving socket.
        if sender:
            try:
                if isinstance(output, VrcftOutput):
                    for address, values in output.shutdown_messages():
                        sender.send(address, values)
                elif output and output.sent_closed:
                    sender.send(BLINK_ADDRESS, (0.,))
            except OSError as exc:
                LOG.warning("Could not send final eyelid reset: %s", exc)
        if backend:
            report(phase="stopping")
            backend.close()
        for resource in (sender, log_file, projection, directory):
            if resource:
                try:
                    resource.close()
                except Exception as exc:
                    LOG.warning("Cleanup: %s", exc)


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    args = parse_args(argv)
    if args.list_profiles:
        for name, (sdk, code, description) in PROFILES.items():
            print(f"{name:12} API={sdk:6} success={str(code):4} {description}")
        return 0
    try:
        if args.list_dlls:
            if args.use_running_runtime:
                _, path = running_runtime_sdk(PROFILES[args.profile][0])
                print(path)
            else:
                for path in dll_candidates(ROOT, PROFILES[args.profile][0]):
                    print(path)
            return 0
        return run(args)
    except KeyboardInterrupt:
        LOG.info("Stopped. Native VRChat eye OSC times out after 10 seconds; VRCFT outputs receive a neutral reset.")
        return 130
    except Exception as exc:
        LOG.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
