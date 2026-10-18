"""Verify the released ZIP with Python removed from the child environment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("gui", "cli"), default="gui")
    args = parser.parse_args()
    package_name = "aGlass2OSC-Windows-x64-" + args.target
    archive = ROOT / "release" / (package_name + ".zip")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert archive.with_suffix(".zip.sha256").read_text().split()[0] == digest
    (ROOT / "tmp").mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="EXE 中文 空格 ", dir=ROOT / "tmp"))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name in z.namelist():
            assert not Path(name).is_absolute() and ".." not in Path(name).parts
        z.extractall(folder)
    app = folder / package_name
    assert (app / "aglass_key.bin").is_file()
    manifest = json.loads((app / "BUILD-MANIFEST.json").read_text("utf-8"))
    if manifest["driver_installer"]:
        assert (app / "drivers/USBip-0.9.8.1-x64.exe").is_file()
    for name, expected in manifest["sha256"].items():
        assert hashlib.sha256((app / name).read_bytes()).hexdigest() == expected, name
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    env["PYTHONHOME"] = str(folder / "NO-PYTHON-HERE")
    if args.target == "cli":
        executable = str(app / "aGlass2OSC-cli.exe")
        commands = [
            [executable, "--self-test"],
            [executable, "--simulate", "--dry-run", "--projection", "fov", "--duration", ".3"],
            [executable, "--key", "--help"],
            [executable, "--help"],
            [executable, "--list-profiles"],
        ]
        assert not (app / "aGlass2OSC.exe").exists()
        assert not list(app.rglob("_tkinter*"))
    else:
        commands = [
            [str(app / "aGlass2OSC-worker.exe"), "--self-test"],
            [str(app / "aGlass2OSC-worker.exe"), "--cli", "--simulate", "--dry-run", "--projection", "fov", "--duration", ".3"],
            [str(app / "aGlass2OSC-worker.exe"), "--key", "--help"],
            [str(app / "aGlass2OSC.exe"), "--self-test", str(folder / "gui-report.json")],
        ]
    results = []
    for command in commands:
        result = subprocess.run(command, cwd=folder, env=env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=40,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        results.append({"command": command, "exit_code": result.returncode, "output": result.stdout + result.stderr})
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
        assert result.returncode == 0, results[-1]
    worker = json.loads(results[0]["output"])
    assert Path(worker["key_file"]) == app / "aglass_key.bin", worker
    gui = None
    if args.target == "gui":
        gui = json.loads((folder / "gui-report.json").read_text("utf-8"))
        assert gui["gui"] == "ok", gui
    report = {"directory": str(app), "sha256": digest, "files_verified": len(manifest["sha256"]),
              "checks": results, "gui": gui}
    (ROOT / f"tmp/exe-{args.target}-release-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print("Portable EXE verification passed")


if __name__ == "__main__":
    main()
