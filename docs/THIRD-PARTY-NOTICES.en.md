# Third-party notices

[简体中文](../THIRD-PARTY-NOTICES.md) | **English** | [日本語](THIRD-PARTY-NOTICES.ja.md)

Original aGlass2OSC code is licensed under the [MIT License](../LICENSE). Third-party components retain their own copyright notices and licenses. This document is a source and license index; it does not replace the full upstream terms or relicense third-party components under MIT.

## 1. Runtime dependencies and components that may be bundled

Versions below match the current dependency lists. See `BUILD-MANIFEST.json` in a portable package for its actual Python version, package versions, and file hashes. GUI and CLI file sets differ; for example, the CLI does not bundle the Tk interface.

| Component | Version / purpose | License and source |
| --- | --- | --- |
| CPython | Python 3.12 x64; portable interpreter and standard library | PSF License Agreement and other licenses included with Python; [license documentation](https://docs.python.org/3.12/license.html) |
| Tcl / Tk | 8.6 series provided by the Python installation; GUI | Tcl/Tk BSD-style terms; see each `license.terms`; [Tcl/Tk licenses](https://www.tcl.tk/software/tcltk/license.html) |
| python-osc | 1.10.2; OSC encoding and transmission | The Unlicense; [attwad/python-osc](https://github.com/attwad/python-osc) |
| pyopenvr (Python package `openvr`) | 2.12.1401; OpenVR Python bindings | BSD-3-Clause, Christopher Bruns and contributors; [cmbruns/pyopenvr](https://github.com/cmbruns/pyopenvr) |
| Valve OpenVR | x64 OpenVR API DLL supplied by the above package; version follows that package | BSD-3-Clause, Valve Corporation; [OpenVR LICENSE](https://github.com/ValveSoftware/openvr/blob/master/LICENSE) |
| usbip (usbip-python) | 0.7.0; virtual USB/IP device support | MIT, Jabez Winston; [jabezwinston/usbip-python](https://github.com/jabezwinston/usbip-python) |
| usbip-win2 | 0.9.8.1 x64; standalone driver installer included by default | BSD-2-Clause, Vadym Hrynchyshyn; [version-specific license](https://github.com/vadimgrn/usbip-win2/blob/v.0.9.8.1/LICENSE.txt) |

The unmodified official usbip-win2 installer is `USBip-0.9.8.1-x64.exe`, with SHA-256:

```text
38cad6d4432b52d5bb9409d9ad03b72fdffc4ada4cd3a48fbeca1a2752a8518a
```

Source: [official 0.9.8.1 release](https://github.com/vadimgrn/usbip-win2/releases/tag/v.0.9.8.1). The driver EXE is excluded from Git sources and the minimal source ZIP. Default builds may download and verify it; `--without-driver` omits it. Other components inside the installer remain subject to their respective licenses.

## 2. Build tools

| Tool | Current version | License and source |
| --- | --- | --- |
| PyInstaller | 6.22.3 | GPL-2.0-or-later with the Bootloader Exception; certain files use Apache-2.0. See `COPYING.txt` and the [official licensing explanation](https://pyinstaller.org/en/stable/license.html) |
| pyinstaller-hooks-contrib | 2026.8 | Standard hooks/files: GPL-2.0-or-later; runtime hooks: Apache-2.0; [project license](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/LICENSE) |

Read PyInstaller's tool license together with its bundling exception; the tool's license alone does not describe the license of all project output. The upstream files for the corresponding versions contain the full terms.

## 3. External software and compatible interfaces

- Obtain [aGlassRuntime](https://www.7invensun.com/filedownload/179638), vendor SDKs, devices, and personal calibration separately. They are absent from standard source and portable packages; 7invensun or the respective rights holders provide their terms.
- [SteamVR / OpenVR](https://github.com/ValveSoftware/openvr), [VRChat OSC](https://docs.vrchat.com/docs/osc-eye-tracking), and [VRCFaceTracking](https://docs.vrcft.io/docs/intro/getting-started) are external software or interfaces this project integrates with. SteamVR, VRChat, and VRCFaceTracking applications are not distributed with this project.
- The [legacy WDM USB/IP driver](https://github.com/cezanne/usbip-win) is a compatibility backend installed separately by the user. The default bundled installer is usbip-win2 as listed above; its license must not be confused with the legacy driver's license.
- The [aGlass VRCFT module](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module) is maintained separately. Its source and module package are not included in standard aGlass2OSC releases.

`aglass_key.bin` is a 202-byte simulated protocol response resource supplied by the project, not vendor firmware or a raw disk image. This description does not change the terms of external Runtime or SDK software.

## 4. License files and attribution

The build collects available license files from the Python installation and dependencies into the portable package's `licenses/` directory. This is a build output directory, not a directory at the source root. Preserve these files, notices inside installers, and required component copyright notices when redistributing. Other components supplied with Python or an installer retain their own notices; this index is not an exhaustive list of all transitive dependencies.

Product names and trademarks belong to their respective owners and identify compatibility targets and sources; they do not imply official authorization, partnership, or endorsement. These three language versions provide explanations and references. Applicable upstream license text takes precedence if a description differs. Update this document and its translations when adding or upgrading dependencies.
