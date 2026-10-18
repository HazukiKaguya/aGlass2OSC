# Windows GUI portable package

[简体中文](WINDOWS_EXE.md) | **English** | [日本語](WINDOWS_EXE.ja.md)

Extract `aGlass2OSC-Windows-x64-gui.zip` completely and run `aGlass2OSC.exe`. Keep the entire folder, including the worker EXE and `_internal/`. No installation of Python, pip, or the Windows App SDK is required.

The default package includes all four GUI pages, Python dependencies for OSC/OpenVR/USB Key, protocol resources, licenses, and a checksum manifest. It contains `drivers/USBip-0.9.8.1-x64.exe` and the simulated response file `aglass_key.bin` beside the application. It does not include vendor SDKs, Runtime, disk images, or a VRCFT module ZIP. Obtain the VRCFT module from its [separate project](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module).

Runtime download: [aGlassRuntime](https://www.7invensun.com/filedownload/179638). Before using real hardware, install the matching Runtime and complete personal calibration.

Use a writable directory. Settings are stored in `aglass-gui.json`. Stop the previous version normally before upgrading, and migrate settings as needed. Start with Simulated Preview to check communication between the GUI and worker, then connect your hardware and Runtime. Desktop FOV projection does not require SteamVR.

The four pages are connection and output, eye tracking settings, advanced settings, and virtual USB Key. Scrollbars disappear when the content fits. The mouse wheel does not change collapsed dropdown selections. Blink output is estimated from validity and does not replace measured eyelid openness.

If usbip-win2 is not installed, manually run the included `drivers/USBip-0.9.8.1-x64.exe` before first use of the virtual Key. Installation requires administrator privileges and may require a restart. An empty Key response path prefers `aglass_key.bin` beside the program. Stop with Stop Key, normal window closure, or Ctrl+C; do not forcibly terminate the worker. The GUI does not install drivers automatically. Hardware, calibration, and authorization must still work in Runtime.

Hardware-free checks:

```powershell
.\aGlass2OSC-worker.exe --self-test
.\aGlass2OSC-worker.exe --cli --simulate --dry-run --projection fov --duration 1
```

The GUI check is `aGlass2OSC.exe --self-test report.json`. It briefly opens a window, runs the simulated preview, stops the worker normally, and writes the results to the specified file. It does not connect to real eye tracking hardware or create a virtual USB device.

For build instructions, see the [English README](README.en.md). EXEs are not code-signed. `BUILD-MANIFEST.json` records dependency versions and file SHA-256 hashes; the ZIP has a separate checksum file. See [third-party notices](THIRD-PARTY-NOTICES.en.md) for component sources and licenses.
