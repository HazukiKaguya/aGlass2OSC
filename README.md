# aGlass2OSC

**简体中文** | [English](README.en.md)

aGlass2OSC 是一款 Windows 眼动桥接工具，可将七鑫易维 aGlass 的眼动数据发送到 VRChat（OSC）或 VRCFaceTracking。提供图形界面和独立命令行程序，支持直连已运行的 aGlass Runtime 1.1 或使用匹配的 SDK，并集成虚拟 USB Key 管理。

Windows 用户可以直接下载便携包使用，无需自行安装 Python 和 Python 依赖。

**Runtime 下载：[aGlassRuntime](https://www.7invensun.com/filedownload/179638)**。实际连接设备前请安装配套 Runtime 并完成校准；Runtime 不包含在本项目便携包中。

## 功能介绍

### 1、眼动与 VRChat 输出
- 支持 VRChat 原生 OSC 眼动输出，可选择合并视线，或在数据源支持时输出双眼独立视线。
- 眨眼估算默认开启，也可以手动关闭。
- 提供视线平滑、中心偏移、水平／垂直增益和方向反转设置，方便调整视线表现。
- 处理过期数据，避免追踪中断后持续发送旧视线。
- 支持自动投影选择、桌面 FOV 映射和显式 SteamVR 投影；桌面模式无需强制启动 SteamVR。

### 2、Runtime 与 SDK 兼容
- **Runtime 1.1 直连模式**通过本机通信使用现有 Runtime，无需加载 SDK DLL，也不会为此拉起第二个 Runtime。
- SDK 模式可选择正在运行的 Runtime 对应的 DLL，并提供 DK I / vi-1 不同 API 版本及 DK II 的兼容配置。
- 支持 DLL 自动查找、接口识别、手动指定和诊断。
- SDK 默认在独立子进程中运行，提供启动与停止超时处理，减少原生 SDK 崩溃或卡住对桥接程序的影响。

### 3、图形界面
采用 Tk/ttk 实现的 **WinUI 3 / Fluent 风格界面**，无需 Windows App SDK。四个页面分别负责：
| 页面 | 功能 |
| --- | --- |
| 连接与输出 | 选择 Runtime／SDK、输出目标，启动或停止桥接 |
| 眼动设置 | 调整视线映射、平滑和眨眼估算 |
| 高级设置 | 配置连接参数、诊断与日志 |
| 虚拟 USB Key | 检查驱动状态，启动或停止 Key |
界面提供运行状态、OSC 包数、运行时间和日志显示，支持保存与重新加载设置。可先使用**模拟预览**检查视线显示，该模式不连接实际设备、不发送 OSC。
启动、页面切换和布局已做响应优化；操作按钮与状态集中显示，增加设置区域的可见空间。收起状态的下拉选单不会被滚轮切换；内容能够完整显示时隐藏滚动条，不拦截无意义的页面滚动。

### 4、虚拟 USB Key
- 在 GUI 中管理 Key，也可以通过 CLI 启动。
- 兼容旧 WDM 驱动与 usbip-win2，可自动选择或手动指定后端。
- 正常停止时执行 detach，并通过异常遗留检查和恢复记录，避免在旧驱动端口未确认释放时继续消耗槽位。
- 便携包附带官方 **usbip-win2 0.9.8.1 x64** 驱动安装程序，按需手动安装。
- 附带 `aglass_key.bin` 模拟协议应答文件；默认优先读取程序旁的 BIN，缺失时回退到内置协议资源。
退出 Key 请使用 GUI 的“停止 Key”、正常关闭窗口或 Ctrl+C，让程序完成清理。强制终止进程仍可能造成驱动资源残留。

### 5、VRCFaceTracking 支持
支持向 aGlass VRCFT 模块发送桥接数据，也支持直接输出 VRCFT Avatar 参数。模块源码、构建和安装包在独立项目 [HTC-Vive-7invensun-aGlass-Module](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module) 维护。
模块使用 Runtime 直连时，无需启动 aGlass2OSC 的眼动桥接；使用模块桥接模式时，将模块配置为 `Source=bridge`。两种方式按实际需求选择。

### 6、GUI 与 CLI 便携版
提供两种附带运行依赖的 Windows x64 便携包，均无需安装 Python：
| 附件 | 使用方式 |
| --- | --- |
| `aGlass2OSC-Windows-x64-gui.zip` | 解压后运行 `aGlass2OSC.exe`，使用图形界面 |
| `aGlass2OSC-Windows-x64-cli.zip` | 解压后在终端运行 `aGlass2OSC-cli.exe`，通过参数控制 |
| `aGlass2OSC-GitHub-source.zip` | 包含 GUI／CLI 构建入口的最小源码包 |
| `*.zip.sha256` | 对应 ZIP 的 SHA-256 校验文件 |

请完整解压便携包并保留 `_internal/` 等配套文件。CLI 支持眼动桥接和 `--key` 子命令；已有 Key 实例运行时无需重复启动。

### 7、源码与构建
- 保留 Python CLI 入口 `aglass2vrc.py`，提供 `run-gui.bat` 和 `run-cli.bat`。
- 使用 `build-gui.bat` 或 `build-cli.bat` 分别构建并验证便携包，两种版本使用独立构建缓存与输出目录。
- 构建包包含依赖许可、文件校验清单及 ZIP 的 SHA-256。
- 最小源码包包含模拟应答 BIN，排除驱动安装程序、厂商 SDK 和历史归档。
- 驱动 EXE 通过 Git 忽略规则及 `export-ignore` 排除；默认构建在本地缺少驱动时下载固定版本的官方安装程序并校验 SHA-256。

**功能范围：**眨眼输出基于眼睛／视线有效性估算，并非原生连续眼睑开合度。不同设备与 Runtime 需使用匹配的 SDK 配置，兼容选项不代表所有组合均已完成实机验证。aGlass Runtime、原厂 SDK、硬件及个人校准需另行准备。

## 使用 Windows GUI

完整解压 **aGlass2OSC-Windows-x64-gui.zip** 后运行 `aGlass2OSC.exe`。保留同目录的 `aGlass2OSC-worker.exe` 和 `_internal/`，最终用户不需要安装 Python。设置保存在 EXE 同目录的 `aglass-gui.json`。

1. 可先点击“模拟预览”，检查界面与视线显示；此模式不连接设备，也不发送 OSC。
2. 实际使用前启动配套 aGlass Runtime，准备设备授权并完成个人校准。
3. 连接方式可选“直连 Runtime 1.1（不加载 DLL）”；该方式使用现有 Runtime 的本机 TCP/UDP，不拉起第二个 Runtime。其他 Runtime / DK II 可选择对应 SDK 配置，并提供配套 x64 DLL。
4. 原生 VRChat 输出选择对应目标，在 VRChat 开启 OSC。桌面使用选择“自动”或“桌面 FOV”；不要求 SteamVR。只有明确选择 SteamVR 投影时才需要它。
5. 点击“开始桥接”，确认有效视线和输出；停止后可保存设置。

眨眼估算默认开启，基于眼睛／视线有效性，并非原生连续眼睑开合度。模拟预览、协议测试通过不代表所有设备与模型都已完成实际验收。

## 使用 Windows CLI

完整解压 **aGlass2OSC-Windows-x64-cli.zip**，保留 `_internal/` 等配套文件，在该目录打开终端：
```powershell
.\aGlass2OSC-cli.exe --help
.\aGlass2OSC-cli.exe --simulate --dry-run --projection fov --duration 3
```
第二条命令只处理模拟数据，不连接设备、不发送 OSC。实际连接已启动的 Runtime 1.1：
```powershell
.\aGlass2OSC-cli.exe --connection runtime --projection fov
```
CLI 保留 Runtime 直连、SDK、OSC 与虚拟 Key 支持。用 `--key --help` 查看 Key 子命令，详见 [docs/CLI.md](docs/CLI.md)。

## 构建 GUI 包

需要 **Windows x64、Python 3.12 x64（包含 Tcl/Tk）** 和可下载 Python 包的网络。无需 .NET SDK、VRCFT 模块工程、原厂 DLL、Runtime 安装包或 USB 驱动安装包即可构建。请使用独立虚拟环境，避免把无关依赖打入 EXE。

在源码根目录的终端运行：
```powershell
.\build-gui.bat
```
脚本自动创建 `.venv`、安装固定版本依赖、构建两个 EXE，并执行不访问硬件的便携包检查。检查期间会短暂显示 GUI。也可以逐步运行：
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/build_exe.py --target gui
.\.venv\Scripts\python.exe tools/check_exe.py --target gui
```
输出为：
```text
release/aGlass2OSC-Windows-x64-gui.zip
release/aGlass2OSC-Windows-x64-gui.zip.sha256
```
每次构建使用新的 `release/build-*` 目录，不清理用户可能正在运行的旧程序。最终 ZIP 内含两个 EXE、共享运行库、说明、许可及文件校验清单。默认包含 `drivers/USBip-0.9.8.1-x64.exe` 和 `aglass_key.bin`。构建优先使用本地驱动，缺失时下载固定版本的官方安装包并核验 SHA-256；`--driver-installer` 可指定已有安装包，`--without-driver` 可显式构建不带驱动的精简包。构建过程不执行驱动安装。

源码运行 GUI：安装上述依赖后执行 `.\.venv\Scripts\python.exe aglass_gui.py`，或使用 `run-gui.bat`。

## 构建 CLI 包

需要与 GUI 构建相同的 **Windows x64、Python 3.12 x64** 和依赖下载环境。在源码根目录运行：
```powershell
.\build-cli.bat
```
脚本自动创建 `.venv`、安装固定版本依赖、构建独立的 `aGlass2OSC-cli.exe`，并执行不访问硬件的便携包检查。CLI 检查不打开图形界面。也可以逐步运行：
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/build_exe.py --target cli
.\.venv\Scripts\python.exe tools/check_exe.py --target cli
```
输出为：
```text
release/aGlass2OSC-Windows-x64-cli.zip
release/aGlass2OSC-Windows-x64-cli.zip.sha256
```

CLI 包同样包含运行依赖、官方驱动安装程序和 `aglass_key.bin`，也支持 `--driver-installer` 与 `--without-driver` 构建选项。GUI 与 CLI 使用独立的构建缓存与输出目录。

源码运行 CLI：安装上述依赖后执行 `.\.venv\Scripts\python.exe aglass2vrc.py --help`，或使用 `run-cli.bat --help`。源码 ZIP 包含 GUI 和 CLI 两种构建入口。

## VRCFaceTracking

**VRCFT 模块的源码、构建与安装包单独维护：**
[HTC-Vive-7invensun-aGlass-Module](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module)

本仓库不构建或附带 C# 模块。GUI 仍支持向该模块发送桥接数据，以及直发 VRCFT Avatar 参数。模块设为 Runtime 直连时无需启动 GUI 的眼动桥接；模块设为 `Source=bridge` 时，GUI 才使用“VRCFT 模块”输出，默认端口为 9015。避免两个客户端同时控制同一 Runtime。

## 虚拟 USB Key 与退出

保留 usbip-win2 与 WDM 驱动兼容功能。完整 GUI／CLI 包均附带官方驱动安装程序；未安装 usbip-win2 的电脑首次使用时手动运行 `drivers/USBip-0.9.8.1-x64.exe`，需要管理员权限，可能需要重启。GUI 不静默安装驱动。

`aglass_key.bin` 是 202 字节的模拟协议应答文件，不是固件镜像；它同时包含在源码和 GUI／CLI 包中。Key 应答路径留空时优先读取程序旁的该文件，缺失时回退到内置 `aglass_vrc/key_protocol.json`，也可手动指定其他应答文件。原始磁盘镜像、厂商 SDK 和个人校准数据不包含在此仓库。

需要退出时使用 GUI 的“停止 Key”、正常关闭窗口，或命令行 Ctrl+C，让程序先 detach 再退出。不要强制结束 Key 后台。旧驱动异常退出后的恢复工具为 `tools/recover_vhci.ps1`，执行前按脚本说明确认影响。

## 上传源码与生成源码 ZIP

开发目录布局和维护流程见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。本地历史材料统一放在 `res/archive/`，不参与构建或源码打包；SDK 自动查找仍可发现其中的 DLL。

仓库保留 GUI／CLI 必需的 Python 模块、协议资源、入口、依赖清单、构建／检查工具和说明。驱动 EXE 被 `.gitignore` 排除，并标记 `export-ignore`；`aglass_key.bin` 明确保留。`release/`、缓存、用户设置及日志均忽略；EXE 安装包作为 GitHub Release 附件上传。
```powershell
python tools/package_source.py
```
该命令按明确文件清单生成 `release/aGlass2OSC-GitHub-source.zip` 及 SHA-256 文件，包含模拟应答 BIN，但排除驱动安装程序，也不会递归收集工作目录中的 SDK、磁盘镜像、缓存或日志。上传源码 ZIP 时先解压，使用其中 `aGlass2OSC/` 目录的内容作为仓库根目录。使用说明见 [docs/WINDOWS_EXE.md](docs/WINDOWS_EXE.md)。

## 许可

本项目使用 [MIT License](LICENSE)。构建包包含 Python、Tk、python-osc、OpenVR、usbip 及打包组件的许可文件。aGlass Runtime、原厂 SDK、硬件需由用户另行准备；第三方驱动安装包随 GUI／CLI 分发。本项目为社区工具。