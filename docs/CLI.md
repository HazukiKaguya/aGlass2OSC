# Windows CLI 使用与构建

CLI 和 GUI 使用同一套桥接实现，支持 Runtime 直连、SDK 配置、VRChat OSC、VRCFT 输出和眨眼估算。CLI 不打开图形界面，也不需要安装 Python。

## 使用便携 EXE

完整解压 `aGlass2OSC-Windows-x64-cli.zip`，保留 `_internal/` 与 `aglass_key.bin`，在该目录打开终端：

```powershell
.\aGlass2OSC-cli.exe --help
.\aGlass2OSC-cli.exe --list-profiles
.\aGlass2OSC-cli.exe --simulate --dry-run --projection fov --duration 3
```

最后一条只处理模拟数据，不发送 OSC，不连接设备。`--self-test` 可检查打包依赖、Key 应答和子进程启动，不访问设备。

实际使用时先启动配套 Runtime、准备设备授权并完成校准，在 VRChat 中开启 OSC：

```powershell
.\aGlass2OSC-cli.exe --connection runtime --projection fov
```

该命令直连现有 Runtime 1.1；桌面 FOV 不需要 SteamVR。省略投影选项时使用 `auto`，在无法获得 SteamVR 投影时回退到 FOV。其他 Runtime 可用 `--profile` 和 `--dll` 指定匹配 SDK；`--list-dlls` 列出安装位置及 `res/` 下的候选 DLL，包括本地归档。便携包不附带原厂 SDK。

默认目标为 VRChat 原生 OSC，端口 9000。`--target vrcft-module` 输出到独立模块的桥接端口；模块需设为 `Source=bridge`。连续眼睑开合度未由此实现，默认眨眼输出是有效性估算。

## 虚拟 USB Key

CLI 包同样附带官方驱动安装程序和模拟应答 BIN。需要虚拟 Key 时，在另一个终端运行：

```powershell
.\aGlass2OSC-cli.exe --key --help
.\aGlass2OSC-cli.exe --key --backend auto
```

首次使用时按需要手动安装 `drivers/USBip-0.9.8.1-x64.exe`，可能需要管理员权限和重启。不要同时运行多个 Key 实例；已有 GUI Key 运行时可继续使用它。使用 Ctrl+C 正常退出，让程序完成 detach。桥接和 Key 是两个独立命令，退出桥接不会关闭另一个终端的 Key。

## 从源码运行或构建

源码运行：

```powershell
python -m pip install -r requirements.txt -r requirements-usbkey.txt
python aglass2vrc.py --help
.\run-cli.bat --simulate --dry-run --projection fov --duration 3
```

`run-cli.bat` 优先使用本目录 `.venv`，不存在时使用 PATH 中的 Python，并转发所有命令行参数和退出码。

使用 Windows x64 Python 3.12 构建：

```powershell
.\build-cli.bat
```

脚本安装固定版本依赖后，执行以下两步；已经准备好环境时可直接调用：

```powershell
.\.venv\Scripts\python.exe tools/build_exe.py --target cli
.\.venv\Scripts\python.exe tools/check_exe.py --target cli
```

产物为 `release/aGlass2OSC-Windows-x64-cli.zip` 及 `.zip.sha256`。CLI 与 GUI 使用独立构建缓存及输出目录。默认附带驱动，`--without-driver` 可显式省略驱动。源码打包 `python tools/package_source.py` 同时保留两种构建入口，但不包含驱动安装程序。
