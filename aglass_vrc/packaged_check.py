"""Explicit, hardware-free checks of the shipped EXEs and their child process."""
import json
from pathlib import Path
import time


def child_check(pipe):
    from .usbkey_device import RecordedKey
    pipe.send({"spawn": True, "key_records": len(RecordedKey().replies)})
    pipe.close()


def worker_check():
    import multiprocessing as mp
    import openvr
    from pythonosc.osc_message_builder import OscMessageBuilder
    from .usbkey_device import ReadOnlyImage, RecordedKey, TRACE, make_device
    device = make_device(ReadOnlyImage(None, "cdrom"), RecordedKey(), "cdrom")
    assert len(device.device_descriptor().pack()) == 18
    OscMessageBuilder(address="/self-test").build()
    assert openvr.VRApplication_Background
    context = mp.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=child_check, args=(child,))
    process.start()
    child.close()
    try:
        if not parent.poll(10):
            raise TimeoutError("Packaged multiprocessing check timed out")
        report = parent.recv()
        process.join(10)
        assert process.exitcode == 0
        print(json.dumps({"worker": "ok", "key_file": str(TRACE), **report}))
    finally:
        parent.close()
        # This worker owns only a hardware-free self-test child.
        if process.is_alive():
            process.terminate()
            process.join(2)
        process.close()
    return 0


def gui_check(destination):
    import tkinter as tk
    from .gui import Application
    report = {}
    root = tk.Tk()
    root.withdraw()
    app = Application(root, Path(destination).with_suffix(".settings.json"))

    def pump(predicate, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            root.update()
            if predicate():
                return
            time.sleep(.02)
        raise TimeoutError("Packaged GUI check timed out")

    try:
        assert len(app.notebook.tabs()) == 4
        # A withdrawn window cannot reveal native image-tile repaint stalls.
        paint_start = time.perf_counter()
        root.deiconify()
        root.update()
        first_paint_ms = (time.perf_counter() - paint_start) * 1000
        navigation_ms = []
        for index in (1, 2, 3, 0):
            started = time.perf_counter()
            app.nav_buttons[index].invoke()
            root.update()
            navigation_ms.append((time.perf_counter() - started) * 1000)
        assert first_paint_ms < 5000, f"First paint stalled: {first_paint_ms:.0f} ms"
        assert sorted(navigation_ms)[2] < 1000, f"Navigation stalled: {navigation_ms}"
        app.preview()  # Simulated data; dry-run sends no OSC and opens no device.
        pump(lambda: app.last_frame is not None or not app.session.active)
        assert app.last_frame is not None, app.error
        assert app.last_frame["dry_run"] and app.last_frame["packets"] == 0
        app.stop()
        pump(lambda: not app.session.active)
        app.save()
        assert app.settings_path.is_file()
        report = {"gui": "ok", "tabs": 4, "frame": app.last_frame,
                  "status": app.status.get(), "settings": str(app.settings_path),
                  "first_paint_ms": round(first_paint_ms, 2),
                  "navigation_ms": [round(value, 2) for value in navigation_ms]}
    except Exception as exc:
        report = {"error": str(exc)}
        raise
    finally:
        app.close()
        if app.session.active:
            pump(lambda: not app.session.active)
        Path(destination).write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
