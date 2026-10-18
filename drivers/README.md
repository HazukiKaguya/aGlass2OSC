# USB/IP driver installer

GUI release packages include `USBip-0.9.8.1-x64.exe` here. Install it manually on first use if usbip-win2 is not already installed; administrator rights and a restart may be required. The app does not silently install drivers.

The installer is excluded from Git and source ZIPs. `python tools/build_exe.py` uses the local installer if present, otherwise downloads the fixed official asset and verifies SHA-256. `--without-driver` explicitly opts out.

Official asset: https://github.com/vadimgrn/usbip-win2/releases/download/v.0.9.8.1/USBip-0.9.8.1-x64.exe

SHA-256: `38cad6d4432b52d5bb9409d9ad03b72fdffc4ada4cd3a48fbeca1a2752a8518a`
