# Contributing

[简体中文](../CONTRIBUTING.md) | **English** | [日本語](CONTRIBUTING.ja.md)

Bug reports, compatibility results, fixes, and translations are welcome. This project maintains the aGlass2OSC Python bridge, GUI, CLI, and virtual USB Key. Report issues or contribute changes for the VRCFT C# module in its [separate repository](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module).

## 1. Report an issue

Search existing issues first. Include as much of the following as possible:

- Windows version, aGlass model, Runtime version, and GUI/CLI release or source commit.
- Connection mode (direct Runtime or SDK), SDK profile/DLL file version, output target, and whether SteamVR is running.
- Reproduction steps, expected and actual behavior, and relevant logs; screenshots help with UI issues.
- For USB Key issues: WDM/usbip-win2 backend, driver version, and status after normal shutdown.

Remove unnecessary personal paths, serial numbers, and other personal information before sharing logs. Do not upload personal calibration files, raw disk images, or SDKs you cannot redistribute. Distinguish simulation results from tests performed while wearing the hardware; blink estimation is not native eyelid openness.

## 2. Set up development

Use Windows x64 and Python 3.12 x64 with Tcl/Tk. From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe aglass_gui.py
.\.venv\Scripts\python.exe aglass2vrc.py --help
```

UI work, simulation, and most tests do not require hardware. Hardware testing requires a matching [aGlassRuntime](https://www.7invensun.com/filedownload/179638), hardware, and calibration data. See [DEVELOPMENT.md](DEVELOPMENT.md) for the directory layout, documented in Chinese.

## 3. Validate changes

In a full development tree containing `tests/`, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

The minimal build source ZIP omits `tests/`; do not report a zero-test run caused by a missing directory as successful validation. For a hardware-free CLI check:

```powershell
.\.venv\Scripts\python.exe aglass2vrc.py --simulate --dry-run --projection fov --duration 3
```

When changing packaging, dependencies, or entry points, build and check the affected targets:

```powershell
.\build-gui.bat
.\build-cli.bat
```

The GUI package check briefly opens a window; the CLI check does not. Package checks use simulated data without connecting to devices or sending OSC. For documentation-only changes, check relative links, language navigation, and the source packaging list. For hardware changes, state which device/Runtime combinations you tested and which remain unverified.

## 4. Submit a pull request

- Keep each PR focused on one issue. Describe the trigger, resulting behavior, and validation.
- Follow the existing code organization. Add regression coverage where useful for behavior fixes and avoid unrelated refactoring.
- Keep Chinese, English, and Japanese READMEs aligned when public features or commands change. Also update translations when changing contribution guidelines or third-party notices.
- When adding or upgrading dependencies, update `requirements*.txt`, [third-party notices](THIRD-PARTY-NOTICES.en.md), and license collection in the build where needed.
- When changing distributed files, review the explicit list in `tools/package_source.py`. Run `python tools/package_source.py` to check source export.

## 5. Files and shutdown

Do not commit `.venv/`, `release/`, `tmp/`, `res/archive/`, user settings, logs, or build caches. Keep historical research in local archives outside the standard build; SDK discovery can still find archived DLLs.

`aglass_key.bin` is an included simulated protocol response resource. Driver EXEs stay out of the source repository. The default build uses the local official installer, downloading and verifying it if missing. Do not change shared Runtime or driver state merely to make a test easier.

After USB Key testing, use Stop Key, close the GUI normally, or press Ctrl+C and allow detach to finish. Do not forcibly terminate the Key process or repeatedly start new instances without checking the previous instance's state.

## 6. License

Original contributions should be distributable under the project's [MIT License](../LICENSE). Preserve copyright notices and licenses for third-party material and identify its source. Inclusion in this repository does not relicense third-party material under MIT. See [THIRD-PARTY-NOTICES.en.md](THIRD-PARTY-NOTICES.en.md).
