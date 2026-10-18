# Windows x64 onedir: a windowed GUI and a console-capable worker share libraries.
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH).parent
build_target = os.environ.get("AGLASS_BUILD_TARGET", "gui")
if build_target not in ("gui", "cli"):
    raise ValueError("Invalid AGLASS_BUILD_TARGET: " + build_target)
datas = [(str(root / "aglass_vrc/key_protocol.json"), "aglass_vrc")]
binaries, hidden = [], ["aglass_vrc.usbkey_runner", "aglass_vrc.cli"]
if build_target == "gui":
    hidden.append("aglass_vrc.gui_runner")
for package in ("usbip",):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hidden += h
# Only the x64 runtime is used; OpenVR's optional OpenGL demo frameworks are not.
binaries += [(source, target) for source, target in collect_dynamic_libs("openvr")
             if Path(source).name == "libopenvr_api_64.dll"]
datas += copy_metadata("openvr")
hidden += ["openvr"]

if build_target == "cli":
    cli = Analysis([str(root / "aglass2vrc.py")], pathex=[str(root)], binaries=binaries,
                   datas=datas, hiddenimports=hidden,
                   excludes=["pytest", "tkinter", "aglass_vrc.gui"],
                   noarchive=False)
    cli_exe = EXE(PYZ(cli.pure), cli.scripts, [], exclude_binaries=True,
                  name="aGlass2OSC-cli", console=True, debug=False, strip=False, upx=False)
    COLLECT(cli_exe, cli.binaries, cli.datas,
            name="aGlass2OSC-Windows-x64-cli", strip=False, upx=False)
else:
    gui = Analysis([str(root / "aglass_gui.py")], pathex=[str(root)], binaries=binaries,
                   datas=datas, hiddenimports=hidden, excludes=["pytest"], noarchive=False)
    worker = Analysis([str(root / "aglass_worker.py")], pathex=[str(root)], binaries=binaries,
                      datas=datas, hiddenimports=hidden, excludes=["pytest"], noarchive=False)
    gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True,
                  name="aGlass2OSC", console=False, debug=False, strip=False, upx=False)
    worker_exe = EXE(PYZ(worker.pure), worker.scripts, [], exclude_binaries=True,
                     name="aGlass2OSC-worker", console=True, debug=False, strip=False, upx=False)
    COLLECT(gui_exe, worker_exe, gui.binaries, gui.datas, worker.binaries, worker.datas,
            name="aGlass2OSC-Windows-x64-gui", strip=False, upx=False)
