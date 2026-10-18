# aGlass2OSC

Windows GUI bridge for 7invensun aGlass eye tracking → VRChat OSC. Supports direct connections to an existing aGlass Runtime 1.1 and compatible SDK modes.

将 aGlass 眼动数据发送到 VRChat 的 Windows 图形界面程序。保留 Runtime 直连、不同 SDK 配置、视线映射、眨眼估算、模拟预览和虚拟 USB Key 四页功能。界面为 Tk/ttk 实现的 WinUI 3 / Fluent 风格，无需 Windows App SDK。

## 使用 Windows GUI

完整解压 **aGlass2OSC-Windows-x64-gui.zip** 后运行 `aGlass2OSC.exe`。保留同目录的 `aGlass2OSC-worker.exe` 和 `_internal/`，最终用户不需要安装 Python。设置保存在 EXE 同目录的 `aglass-gui.json`。

1. 可先点击“模拟预览”，检查界面与视线显示；此模式不连接设备，也不发送 OSC。
2. 实际使用前启动配套 aGlass Runtime，准备设备授权并完成个人校准。
3. 连接方式可选“直连 Runtime 1.1（不加载 DLL）”；该方式使用现有 Runtime 的本机 TCP/UDP，不拉起第二个 Runtime。其他 Runtime / DK II 可选择对应 SDK 配置，并提供配套 x64 DLL。
4. 原生 VRChat 输出选择对应目标，在 VRChat 开启 OSC。桌面使用选择“自动”或“桌面 FOV”；不要求 SteamVR。只有明确选择 SteamVR 投影时才需要它。
5. 点击“开始桥接”，确认有效视线和输出；停止后可保存设置。

眨眼估算默认开启，基于眼睛／视线有效性，并非原生连续眼睑开合度。模拟预览、协议测试通过不代表所有设备与模型都已完成实际验收。

## 构建最小 GUI 包

需要 **Windows x64、Python 3.12 x64（包含 Tcl/Tk）** 和可下载 Python 包的网络。无需 .NET SDK、VRCFT 模块工程、原厂 DLL、Runtime 安装包或 USB 驱动安装包即可构建。请使用独立虚拟环境，避免把无关依赖打入 EXE。

在源码根目录的终端运行：

```powershell
.\build-gui.bat
```

脚本自动创建 `.venv`、安装固定版本依赖、构建两个 EXE，并执行不访问硬件的便携包检查。检查期间会短暂显示 GUI。也可以逐步运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/build_exe.py
.\.venv\Scripts\python.exe tools/check_exe.py
```

输出为：

```text
release/aGlass2OSC-Windows-x64-gui.zip
release/aGlass2OSC-Windows-x64-gui.zip.sha256
```

每次构建使用新的 `release/build-*` 目录，不清理用户可能正在运行的旧程序。最终 ZIP 内含两个 EXE、共享运行库、说明、许可及文件校验清单。默认包含 `drivers/USBip-0.9.8.1-x64.exe` 和 `aglass_key.bin`。构建优先使用本地驱动，缺失时下载固定版本的官方安装包并核验 SHA-256；`--driver-installer` 可指定已有安装包，`--without-driver` 可显式构建不带驱动的精简包。构建过程不执行驱动安装。

源码运行 GUI：安装上述依赖后执行 `.\.venv\Scripts\python.exe aglass_gui.py`，或使用 `run-gui.bat`。

## 命令行版本（CLI）

Python CLI 入口仍为 `aglass2vrc.py`，可用 `run-cli.bat --help` 查看参数。独立 EXE 使用 `build-cli.bat` 构建，输出 `release/aGlass2OSC-Windows-x64-cli.zip`，解压后运行 `aGlass2OSC-cli.exe --help`。CLI 保留 Runtime 直连、SDK、OSC 与虚拟 Key 支持，详见 [docs/CLI.md](docs/CLI.md)。源码 ZIP 包含 GUI 和 CLI 两种构建入口。

## VRCFaceTracking

**VRCFT 模块的源码、构建与安装包单独维护：**
[HTC-Vive-7invensun-aGlass-Module](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module)

本仓库不构建或附带 C# 模块。GUI 仍支持向该模块发送桥接数据，以及直发 VRCFT Avatar 参数。模块设为 Runtime 直连时无需启动 GUI 的眼动桥接；模块设为 `Source=bridge` 时，GUI 才使用“VRCFT 模块”输出，默认端口为 9015。避免两个客户端同时控制同一 Runtime。

## 虚拟 USB Key 与退出

保留 usbip-win2 与旧 WDM 驱动兼容功能。完整 GUI 包已附带官方驱动安装程序；未安装 usbip-win2 的电脑首次使用时手动运行 `drivers/USBip-0.9.8.1-x64.exe`，需要管理员权限，可能需要重启。GUI 不静默安装驱动。

`aglass_key.bin` 是 202 字节的模拟协议应答文件，不是固件镜像；它同时包含在源码和 GUI 包中。Key 应答路径留空时优先读取程序旁的该文件，缺失时回退到内置 `aglass_vrc/key_protocol.json`，也可手动指定其他应答文件。原始磁盘镜像、厂商 SDK 和个人校准数据不包含在此仓库。

需要退出时使用 GUI 的“停止 Key”、正常关闭窗口，或命令行 Ctrl+C，让程序先 detach 再退出。不要强制结束 Key 后台。旧驱动异常退出后的恢复工具为 `tools/recover_vhci.ps1`，执行前按脚本说明确认影响。

## 上传源码与生成源码 ZIP

开发目录布局和维护流程见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。本地历史材料统一放在 `res/archive/`，不参与构建或源码打包；SDK 自动查找仍可发现其中的 DLL。

仓库仅保留 GUI 必需的 Python 模块、协议资源、入口、依赖清单、构建／检查工具和说明。驱动 EXE 被 `.gitignore` 排除，并标记 `export-ignore`；`aglass_key.bin` 明确保留。`release/`、缓存、用户设置及日志均忽略；EXE 安装包作为 GitHub Release 附件上传。

```powershell
python tools/package_source.py
```

该命令按明确文件清单生成 `release/aGlass2OSC-GitHub-source.zip` 及 SHA-256 文件，包含模拟应答 BIN，但排除驱动安装程序，也不会递归收集工作目录中的 SDK、磁盘镜像、缓存或日志。上传源码 ZIP 时先解压，使用其中 `aGlass2OSC/` 目录的内容作为仓库根目录。使用说明见 [docs/WINDOWS_EXE.md](docs/WINDOWS_EXE.md)。

## 许可

本项目使用 [MIT License](LICENSE)。构建包包含 Python、Tk、python-osc、OpenVR、usbip 及打包组件的许可文件。aGlass Runtime、原厂 SDK、硬件需由用户另行准备；第三方驱动安装包随 GUI 分发。本项目为社区工具。
