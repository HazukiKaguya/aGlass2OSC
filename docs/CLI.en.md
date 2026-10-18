# Windows CLI usage and builds

[简体中文](CLI.md) | **English** | [日本語](CLI.ja.md)

The CLI shares the GUI's bridge implementation: direct Runtime connections, SDK profiles, VRChat OSC, VRCFT output, and blink estimation. The portable CLI does not open a graphical interface or require a Python installation.

## Use the portable EXE

Extract `aGlass2OSC-Windows-x64-cli.zip` completely, retain `_internal/` and `aglass_key.bin`, and open a terminal in that directory:

```powershell
.\aGlass2OSC-cli.exe --help
.\aGlass2OSC-cli.exe --list-profiles
.\aGlass2OSC-cli.exe --simulate --dry-run --projection fov --duration 3
```

The last command only processes simulated data; it does not send OSC or connect to devices. `--self-test` checks packaged dependencies, Key responses, and child-process startup without accessing hardware.

For real use, obtain the matching [aGlassRuntime](https://www.7invensun.com/filedownload/179638), start it, prepare device authorization, complete calibration, and enable OSC in VRChat:

```powershell
.\aGlass2OSC-cli.exe --connection runtime --projection fov
```

This connects directly to the existing Runtime 1.1. Desktop FOV does not require SteamVR. Omitting the projection option uses `auto`, falling back to FOV when SteamVR projection is unavailable. For other Runtime versions, use `--profile` and `--dll` to select a matching SDK. `--list-dlls` lists candidates in installation locations and under `res/`, including local archives. Portable packages do not include vendor SDKs.

The default target is native VRChat OSC on port 9000. `--target vrcft-module` sends to the separate module's bridge port; configure the module with `Source=bridge`. Continuous eyelid openness is not implemented; default blink output is estimated from validity.

## Virtual USB Key

The CLI package also includes the official driver installer and simulated response BIN. If a virtual Key is needed, use a separate terminal:

```powershell
.\aGlass2OSC-cli.exe --key --help
.\aGlass2OSC-cli.exe --key --backend auto
```

Manually install `drivers/USBip-0.9.8.1-x64.exe` if needed before first use. Administrator privileges and a restart may be required. Do not run multiple Key instances; an existing GUI Key can remain in use. Exit normally with Ctrl+C to allow detach. The bridge and Key are separate commands: stopping the bridge does not stop the Key in another terminal.

## Run or build from source

Run from the source root:

```powershell
python -m pip install -r requirements.txt -r requirements-usbkey.txt
python aglass2vrc.py --help
.\run-cli.bat --simulate --dry-run --projection fov --duration 3
```

`run-cli.bat` prefers the project's `.venv`, otherwise uses Python from PATH, and forwards arguments and the exit code.

Build with Windows x64 and Python 3.12 x64:

```powershell
.\build-cli.bat
```

After installing pinned dependencies, the script runs the following steps. You may run them directly when the environment is ready:

```powershell
.\.venv\Scripts\python.exe tools/build_exe.py --target cli
.\.venv\Scripts\python.exe tools/check_exe.py --target cli
```

Outputs are `release/aGlass2OSC-Windows-x64-cli.zip` and its `.zip.sha256`. GUI and CLI use separate build caches and output directories. The driver is included by default; `--without-driver` explicitly omits it. `python tools/package_source.py` exports source with both build entry points but without the driver installer.

See the [English README](README.en.md), [contribution guide](CONTRIBUTING.en.md), and [third-party notices](THIRD-PARTY-NOTICES.en.md).
