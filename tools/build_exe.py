"""Build a self-contained Windows x64 GUI or CLI ZIP."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DRIVER_SHA = "38cad6d4432b52d5bb9409d9ad03b72fdffc4ada4cd3a48fbeca1a2752a8518a"

DRIVER_URL = "https://github.com/vadimgrn/usbip-win2/releases/download/v.0.9.8.1/USBip-0.9.8.1-x64.exe"


def prepare_driver(path):
    """Use a local verified installer, or fetch the pinned official asset."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(path.suffix + ".partial")
        try:
            print("Downloading official USB/IP driver: " + DRIVER_URL, flush=True)
            request = urllib.request.Request(DRIVER_URL, headers={"User-Agent": "aGlass2OSC-build"})
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output, length=64 * 1024)
            if hashlib.sha256(partial.read_bytes()).hexdigest() != DRIVER_SHA:
                raise ValueError("Downloaded driver installer checksum mismatch")
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
    if hashlib.sha256(path.read_bytes()).hexdigest() != DRIVER_SHA:
        raise ValueError("Driver installer does not match the verified official 0.9.8.1 x64 asset")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("gui", "cli"), default="gui")
    driver_options = parser.add_mutually_exclusive_group()
    driver_options.add_argument("--driver-installer", type=Path, help="use an existing official USBip-0.9.8.1-x64.exe")
    driver_options.add_argument("--without-driver", action="store_true", help="explicitly build a smaller package without the installer")
    args = parser.parse_args()
    name = "aGlass2OSC-Windows-x64-" + args.target
    if os.name != "nt" or sys.maxsize <= 2**32:
        parser.error("Build on 64-bit Windows Python with Tcl/Tk.")
    if not (ROOT / "aglass_key.bin").is_file():
        parser.error("Required simulated response file is missing: aglass_key.bin")
    if not args.without_driver:
        if args.driver_installer and not args.driver_installer.is_file():
            parser.error("Explicit driver installer path does not exist")
        args.driver_installer = prepare_driver(args.driver_installer or ROOT / "drivers/USBip-0.9.8.1-x64.exe")
    # Never let PyInstaller clean a distribution the user may be running.
    # Each build has its own directory; the stable ZIP is the delivery artifact.
    (ROOT / "release").mkdir(exist_ok=True)
    distribution = Path(tempfile.mkdtemp(prefix="build-", dir=ROOT / "release"))
    output = distribution / name
    assert output.resolve().is_relative_to((ROOT / "release").resolve())
    environment = dict(os.environ, AGLASS_BUILD_TARGET=args.target)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                    "--distpath", str(distribution), "--workpath", str(ROOT / "tmp/pyinstaller" / args.target),
                    str(ROOT / "tools/aGlass2OSC.spec")], cwd=ROOT, env=environment, check=True)
    for filename in ("README.md", "LICENSE", "aglass_key.bin"):
        shutil.copy2(ROOT / filename, output / filename)
    (output / "docs").mkdir(exist_ok=True)
    for source in (ROOT / "docs").glob("*.md"):
        shutil.copy2(source, output / "docs" / source.name)
    (output / "tools").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "tools/recover_vhci.ps1", output / "tools/recover_vhci.ps1")
    start_here = "CLI.md" if args.target == "cli" else "WINDOWS_EXE.md"
    shutil.copy2(ROOT / "docs" / start_here, output / "START-HERE.md")
    versions = {}
    licenses = output / "licenses"
    licenses.mkdir(exist_ok=True)
    for package in ("python-osc", "openvr", "usbip", "pyinstaller", "pyinstaller-hooks-contrib"):
        dist = metadata.distribution(package)
        versions[package] = dist.version
        license_text = dist.metadata.get("License")
        if license_text:
            (licenses / (package + "-LICENSE.txt")).write_text(license_text, "utf-8")
        for entry in dist.files or []:
            if "license" in entry.name.lower() or "copying" in entry.name.lower():
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    target = licenses / package / str(entry).replace("../", "").replace("..\\", "")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    for component in ("tcl8.6", "tk8.6"):
        source = Path(sys.base_prefix) / "tcl" / component / "license.terms"
        if source.is_file():
            shutil.copy2(source, licenses / (component + "-license.terms"))
    if args.driver_installer:
        drivers = output / "drivers"
        drivers.mkdir(exist_ok=True)
        shutil.copy2(args.driver_installer, drivers / "USBip-0.9.8.1-x64.exe")
        (drivers / "README.txt").write_text(
            "Official usbip-win2 0.9.8.1 x64 installer (optional). Run only if the driver is not installed.\n"
            "https://github.com/vadimgrn/usbip-win2/releases/tag/v.0.9.8.1\n"
            f"SHA-256: {DRIVER_SHA}\nInstallation requires administrator rights and may require a Windows restart.\n", "utf-8")
    files = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in output.rglob("*") if p.is_file()}
    (output / "BUILD-MANIFEST.json").write_text(json.dumps(
        {"target": args.target, "python": sys.version, "packages": versions, "driver_installer": bool(args.driver_installer), "sha256": files},
        ensure_ascii=False, indent=2), "utf-8")
    archive = ROOT / "release" / (name + ".zip")
    partial = archive.with_suffix(".zip.partial")
    with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as z:
        for path in output.rglob("*"):
            if path.is_file():
                z.write(path, name + "/" + path.relative_to(output).as_posix())
    with zipfile.ZipFile(partial) as z:
        assert z.testzip() is None
    partial.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "  " + archive.name + "\n", "utf-8")
    print(json.dumps({"archive": str(archive), "directory": str(output), "bytes": archive.stat().st_size,
                      "files": len(files) + 1, "sha256": digest}))


if __name__ == "__main__":
    main()
