# aGlass2OSC

[简体中文](../README.md) | **English** | [日本語](README.ja.md)

aGlass2OSC is a Windows eye tracking bridge that sends gaze data from 7invensun aGlass to VRChat via OSC or to VRCFaceTracking. It provides a graphical interface and a standalone command-line application, supports direct connections to an already running aGlass Runtime 1.1 or a matching SDK, and includes virtual USB Key management.

Windows users can download a portable package and run it without installing Python or Python dependencies.

**Runtime download: [aGlassRuntime](https://www.7invensun.com/filedownload/179638)**. Install the matching Runtime and complete calibration before using real hardware. The Runtime is not included in this project's portable packages.

## Features

### 1. Eye tracking and VRChat output

- Native VRChat OSC eye tracking output, with combined gaze or separate gaze for each eye when supported by the data source.
- Blink estimation enabled by default, with an option to turn it off.
- Gaze smoothing, center offsets, horizontal/vertical gain, and axis inversion to adjust gaze behavior.
- Stale-data handling to avoid continually sending old gaze samples after tracking stops.
- Automatic projection selection, desktop FOV mapping, and explicit SteamVR projection. Desktop mode does not require SteamVR.

### 2. Runtime and SDK compatibility

- **Direct Runtime 1.1 mode** communicates locally with the existing Runtime without loading an SDK DLL or starting a second Runtime.
- SDK mode can select the DLL associated with the running Runtime. Profiles are available for different DK I / vi-1 API versions and DK II.
- DLL discovery, interface detection, manual DLL selection, and diagnostics.
- The SDK runs in a separate process by default, with startup and shutdown timeouts to reduce the impact of native SDK crashes or hangs on the bridge.

### 3. Graphical interface

A **WinUI 3 / Fluent-style interface** implemented with Tk/ttk, without requiring the Windows App SDK. Its four pages provide:

| Page | Features |
| --- | --- |
| Connection and output | Select Runtime/SDK and output targets; start or stop the bridge |
| Eye tracking settings | Adjust gaze mapping, smoothing, and blink estimation |
| Advanced settings | Configure connection parameters, diagnostics, and logging |
| Virtual USB Key | Check driver status; start or stop the Key |

The interface displays session status, OSC packet counts, elapsed time, and logs, and can save and reload settings. Use **Simulated Preview** to check the gaze display without connecting to hardware or sending OSC.

Startup, page switching, and layout responsiveness have been improved. Controls and status are grouped to leave more room for settings. The mouse wheel does not change collapsed dropdown selections. When all content fits, scrollbars are hidden and unnecessary page scrolling is disabled.

### 4. Virtual USB Key

- Manage the Key in the GUI or start it from the CLI.
- Supports the legacy WDM driver and usbip-win2, with automatic or manual backend selection.
- Detaches on normal shutdown and records recovery state. Checks for leftover devices help prevent consuming additional legacy driver slots when a previous port has not been confirmed released.
- Portable packages include the official **usbip-win2 0.9.8.1 x64** driver installer for manual installation when needed.
- Includes `aglass_key.bin`, a simulated protocol response file. The application prefers the BIN beside it and falls back to bundled protocol resources if the file is absent.

Exit with **Stop Key**, close the GUI normally, or press Ctrl+C so cleanup can finish. Forcibly terminating the process can still leave driver resources allocated.

### 5. VRCFaceTracking support

Send bridge data to the aGlass VRCFT module, or output VRCFT avatar parameters directly. Module source, builds, and installation packages are maintained separately in [HTC-Vive-7invensun-aGlass-Module](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module).

When the module connects directly to Runtime, the aGlass2OSC eye tracking bridge is unnecessary. To use the module's bridge mode, configure it with `Source=bridge`. Choose the mode that suits your setup.

### 6. GUI and CLI portable packages

Two Windows x64 portable packages include their runtime dependencies and do not require a Python installation:

| Asset | Usage |
| --- | --- |
| `aGlass2OSC-Windows-x64-gui.zip` | Extract and run `aGlass2OSC.exe` for the graphical interface |
| `aGlass2OSC-Windows-x64-cli.zip` | Extract and run `aGlass2OSC-cli.exe` in a terminal with command-line options |
| `aGlass2OSC-GitHub-source.zip` | Minimal source package with both GUI and CLI build entry points |
| `*.zip.sha256` | SHA-256 checksum for the corresponding ZIP |

Extract the entire package and retain `_internal/` and other companion files. The CLI provides eye tracking commands and a `--key` subcommand. Do not start another Key instance if one is already running.

### 7. Source and builds

- Retains the Python CLI entry point `aglass2vrc.py`, with `run-gui.bat` and `run-cli.bat` launchers.
- Use `build-gui.bat` or `build-cli.bat` to build and verify each portable package. The two targets have separate caches and output directories.
- Built packages include dependency licenses, a file checksum manifest, and a SHA-256 checksum for the ZIP.
- The minimal source package includes the simulated response BIN and excludes driver installers, vendor SDKs, and historical archives.
- Driver EXEs are excluded by Git ignore rules and `export-ignore`. By default, if the local installer is missing, the build downloads the pinned official release and verifies its SHA-256.

**Scope:** Blink output is estimated from eye/gaze validity, not measured continuous eyelid openness. Use the matching SDK profile for your device and Runtime; available profiles do not mean every combination has been verified on hardware. Obtain aGlass Runtime, vendor SDKs, and hardware separately, and complete personal calibration.

## Use the Windows GUI

Extract **aGlass2OSC-Windows-x64-gui.zip** completely and run `aGlass2OSC.exe`. Keep `aGlass2OSC-worker.exe` and `_internal/` beside it. End users do not need to install Python. Settings are saved to `aglass-gui.json` beside the executable.

1. Start with **Simulated Preview** to check the interface and gaze display. This mode does not connect to hardware or send OSC.
2. Before using real hardware, start the matching aGlass Runtime, prepare device authorization, and complete personal calibration.
3. Select **Direct Runtime 1.1 (no DLL)** to communicate with the existing Runtime over local TCP/UDP without starting a second Runtime. For other Runtime versions or DK II, select the matching SDK profile and provide its x64 DLL.
4. For native VRChat output, select the corresponding output target and enable OSC in VRChat. Desktop use supports **Auto** or **Desktop FOV** and does not require SteamVR. Explicit SteamVR projection requires SteamVR to be available.
5. Start the bridge, confirm valid gaze data and output, then stop it and save your settings as needed.

Blink estimation is enabled by default and uses eye/gaze validity. It is not a measurement of continuous eyelid openness. Passing simulation and protocol tests does not establish compatibility with every device or avatar.

## Use the Windows CLI

Extract **aGlass2OSC-Windows-x64-cli.zip** completely, retain `_internal/` and the other companion files, and open a terminal in that directory:

```powershell
.\aGlass2OSC-cli.exe --help
.\aGlass2OSC-cli.exe --simulate --dry-run --projection fov --duration 3
```

The second command processes simulated data without connecting to hardware or sending OSC. To connect to an already running Runtime 1.1:

```powershell
.\aGlass2OSC-cli.exe --connection runtime --projection fov
```

The CLI supports direct Runtime connections, SDK modes, OSC output, and the virtual USB Key. Use `--key --help` for Key commands. See the [CLI guide](CLI.en.md) for additional instructions.

## Build the GUI package

Requirements: **Windows x64, Python 3.12 x64 with Tcl/Tk**, and network access to download Python packages. Building does not require the .NET SDK, VRCFT module project, vendor DLLs, or a Runtime installer. You do not need to obtain the USB driver installer manually; the build can download it. Use a dedicated virtual environment to avoid bundling unrelated dependencies.

Run from a terminal in the source root:

```powershell
.\build-gui.bat
```

The script creates `.venv`, installs pinned dependencies, builds both executables, and checks the portable package without accessing hardware. The check briefly opens the GUI. Alternatively, run each step:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/build_exe.py --target gui
.\.venv\Scripts\python.exe tools/check_exe.py --target gui
```

Outputs:

```text
release/aGlass2OSC-Windows-x64-gui.zip
release/aGlass2OSC-Windows-x64-gui.zip.sha256
```

Each build uses a new `release/build-*` directory so it does not clean an older program you may still be running. The ZIP contains both executables, shared runtime libraries, documentation, licenses, and a file checksum manifest. By default it includes `drivers/USBip-0.9.8.1-x64.exe` and `aglass_key.bin`. The build uses the local driver installer when available; otherwise it downloads the pinned official release and verifies its SHA-256. Use `--driver-installer` to supply an existing installer, or `--without-driver` to explicitly omit it. Building does not install the driver.

To run the GUI from source after installing these dependencies, use `.\.venv\Scripts\python.exe aglass_gui.py` or `run-gui.bat`.

## Build the CLI package

Use the same **Windows x64, Python 3.12 x64** environment and dependency download access as the GUI build. Run from the source root:

```powershell
.\build-cli.bat
```

The script creates `.venv`, installs pinned dependencies, builds the standalone `aGlass2OSC-cli.exe`, and checks the portable package without accessing hardware. The CLI check does not open a graphical interface. Alternatively, run each step:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/build_exe.py --target cli
.\.venv\Scripts\python.exe tools/check_exe.py --target cli
```

Outputs:

```text
release/aGlass2OSC-Windows-x64-cli.zip
release/aGlass2OSC-Windows-x64-cli.zip.sha256
```

The CLI package also includes runtime dependencies, the official driver installer, and `aglass_key.bin`. It supports the same `--driver-installer` and `--without-driver` build options. GUI and CLI builds use separate caches and output directories.

To run the CLI from source after installing these dependencies, use `.\.venv\Scripts\python.exe aglass2vrc.py --help` or `run-cli.bat --help`. The source ZIP includes both GUI and CLI build entry points.

## VRCFaceTracking

**The VRCFT module source, builds, and installation package are maintained separately:**
[HTC-Vive-7invensun-aGlass-Module](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module)

This repository does not build or bundle the C# module. The GUI can send bridge data to that module or output VRCFT avatar parameters directly. When the module connects directly to Runtime, you do not need to start the GUI's eye tracking bridge. When the module is configured with `Source=bridge`, select the VRCFT module output in the GUI; its default port is 9015. Avoid having two clients control the same Runtime simultaneously.

## Virtual USB Key and shutdown

Both usbip-win2 and the legacy WDM driver are supported. The complete GUI and CLI packages include the official driver installer. If usbip-win2 is not installed, manually run `drivers/USBip-0.9.8.1-x64.exe` before first use. Installation requires administrator privileges and may require a restart. The GUI does not silently install drivers.

`aglass_key.bin` is a 202-byte simulated protocol response file, not a firmware image. It is included in the source and GUI/CLI packages. Leaving the Key response path empty uses this file beside the application when available, otherwise falling back to the bundled `aglass_vrc/key_protocol.json`. You may also specify another response file. Original disk images, vendor SDKs, and personal calibration data are not included in this repository.

To exit, use **Stop Key**, close the GUI normally, or press Ctrl+C in the terminal so the program can detach the device first. Do not forcibly terminate the Key worker. The recovery tool for legacy driver issues after abnormal termination is `tools/recover_vhci.ps1`; review its instructions and effects before running it.

## Publish source and generate the source ZIP

See [docs/DEVELOPMENT.md](DEVELOPMENT.md) for the development layout and workflow, documented in Chinese. Local historical material is kept in `res/archive/` and excluded from builds and source packages. SDK discovery can still find DLLs there.

The source tree retains the Python modules, protocol resources, entry points, dependency lists, build/check tools, and documentation needed for the GUI and CLI. Driver EXEs are excluded by `.gitignore` and marked `export-ignore`; `aglass_key.bin` is explicitly retained. `release/`, caches, user settings, and logs are ignored. Upload the portable executable packages as GitHub Release assets.

```powershell
python tools/package_source.py
```

This command creates `release/aGlass2OSC-GitHub-source.zip` and its SHA-256 file from an explicit file list. It includes the simulated response BIN but excludes the driver installer. It does not recursively collect SDKs, disk images, caches, or logs from the workspace. Extract the source ZIP and use the contents of its `aGlass2OSC/` directory as the repository root. See the [GUI guide](WINDOWS_EXE.en.md) for additional instructions.

## Contributing and third-party notices

See the [contribution guide](CONTRIBUTING.en.md) for issue reports, development checks, and pull requests. See [third-party notices](THIRD-PARTY-NOTICES.en.md) for component sources and licenses. Both documents are available in Chinese, English, and Japanese.

## License

This project uses the [MIT License](../LICENSE). Built packages include license files for Python, Tk, python-osc, OpenVR, usbip, and packaging components. Obtain aGlass Runtime, vendor SDKs, and hardware separately; the third-party driver installer is distributed with the GUI/CLI packages. This is a community project.
