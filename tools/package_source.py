"""Export only the files required to build the Windows GUI and CLI."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('.gitattributes',
 '.gitignore',
 'LICENSE',
 'README.md',
 'aglass2vrc.py',
 'aglass_gui.py',
 'aglass_key.bin',
 'aglass_vrc/__init__.py',
 'aglass_vrc/app_paths.py',
 'aglass_vrc/cli.py',
 'aglass_vrc/fluent.py',
 'aglass_vrc/gui.py',
 'aglass_vrc/gui_runner.py',
 'aglass_vrc/gui_support.py',
 'aglass_vrc/key_protocol.json',
 'aglass_vrc/module_watch.py',
 'aglass_vrc/packaged_check.py',
 'aglass_vrc/runtime.py',
 'aglass_vrc/runtime_client.py',
 'aglass_vrc/sdk.py',
 'aglass_vrc/sdk_process.py',
 'aglass_vrc/soft_dongle.py',
 'aglass_vrc/tracking.py',
 'aglass_vrc/usbip_win2.py',
 'aglass_vrc/usbkey_device.py',
 'aglass_vrc/usbkey_lifecycle.py',
 'aglass_vrc/usbkey_runner.py',
 'aglass_vrc/vhci.py',
 'aglass_vrc/vrcft.py',
 'aglass_worker.py',
 'build-gui.bat',
 'build-cli.bat',
 'docs/DEVELOPMENT.md',
 'docs/CLI.md',
 'docs/WINDOWS_EXE.md',
 'drivers/README.md',
 'requirements-build.txt',
 'requirements-usbkey.txt',
 'requirements.txt',
 'run-gui.bat',
 'run-cli.bat',
 'tools/aGlass2OSC.spec',
 'tools/build_exe.py',
 'tools/check_exe.py',
 'tools/package_source.py',
 'tools/recover_vhci.ps1')


def main():
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    archive = release / 'aGlass2OSC-GitHub-source.zip'
    for name in FILES:
        if not (ROOT / name).is_file():
            raise FileNotFoundError('Required source file is missing: ' + name)
    partial = archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            z.write(ROOT / name, 'aGlass2OSC/' + name)
    with zipfile.ZipFile(partial) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(FILES)
    partial.replace(archive)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(checksum + '  ' + archive.name + '\n', encoding='utf-8')
    print(f'{len(FILES)} files; {archive.stat().st_size} bytes; {archive}')


if __name__ == '__main__':
    main()
