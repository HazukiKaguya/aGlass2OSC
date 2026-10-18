# 开发目录与标准构建流程

本目录只维护 aGlass2OSC Windows GUI、CLI、Python 桥接和 USB Key 支持。VRCFT C# 模块在独立仓库 [HTC-Vive-7invensun-aGlass-Module](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module) 构建，不需要为 GUI 安装 .NET SDK。

## 目录约定

| 路径 | 用途 |
| --- | --- |
| `aglass_vrc/` | 当前 Python 实现与内置协议资源 |
| `aglass_gui.py`、`aglass_worker.py`、`aglass2vrc.py` | GUI、打包后台及命令行入口 |
| `aglass_key.bin` | 随源码和 GUI 分发的模拟应答文件 |
| `requirements*.txt` | 固定版本运行、USB Key 与构建依赖 |
| `tools/` | 当前构建、包检查、源码导出、GUI 性能检查与驱动恢复工具 |
| `tests/` | 本地完整开发树的回归测试；最小构建源码 ZIP 不包含测试 |
| `docs/` | 当前使用与开发说明 |
| `drivers/` | 官方驱动安装包及来源说明；EXE 不进入 Git 源码 |
| `.venv/` | 本地 Python 环境，可按依赖清单重建 |
| `release/` | 当前构建产物和校验和，不作为源码提交 |
| `tmp/` | 构建缓存、检查日志和解压检查目录 |
| `res/archive/` | 仅供人工查阅的 SDK、旧代码、调查材料与历史备份 |

旧材料不要重新放回根目录、`tools/` 或 `docs/`。需要留存时归入 `res/archive/` 下的日期目录，并记下来源。SDK 自动查找继续扫描 `res/` 下的 DLL，包括归档；归档不作为构建输入。厂商 Runtime 仍由用户另行安装。

## 安装与验证

在项目根目录使用 Windows x64 Python 3.12（包含 Tcl/Tk）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

测试命令适用于包含 `tests/` 的完整开发树。涉及原厂 DLL 的可选测试在 DLL 不存在时跳过；标准回归测试不从归档加载 DLL。最小源码 ZIP 只包含 GUI 构建和便携包验证所需文件，解压后使用下面的构建流程。

## 构建与分发

```powershell
.\build-gui.bat
.\build-cli.bat
.\.venv\Scripts\python.exe tools/package_source.py
```

`build-gui.bat` 安装依赖、运行 `tools/build_exe.py`，再执行 `tools/check_exe.py`。`build-cli.bat` 使用相同工具的 `--target cli` 模式，详见 [CLI.md](CLI.md)。便携包检查会短暂打开 GUI，验证打包依赖、模拟预览、设置保存及正常退出；不会连接眼动设备或发送 OSC。

标准输出：

- `release/aGlass2OSC-Windows-x64-gui.zip` 及 `.zip.sha256`：完整 GUI、Python 依赖、模拟应答 BIN 和官方驱动安装包。
- `release/aGlass2OSC-Windows-x64-cli.zip` 及 `.zip.sha256`：独立命令行 EXE、依赖、模拟应答 BIN 和官方驱动安装包。
- `release/aGlass2OSC-GitHub-source.zip` 及 `.zip.sha256`：按白名单导出的最小构建源码，包含 GUI／CLI 构建入口及 BIN，排除驱动 EXE、归档、个人设置和缓存。

驱动优先读取 `drivers/USBip-0.9.8.1-x64.exe`；缺失时构建脚本下载固定版本并校验 SHA-256。构建不会安装驱动。Git 忽略规则与 `export-ignore` 排除驱动 EXE。

每次构建使用独立的 `release/build-*`，检查工具也使用独立临时目录。清理这些可再生目录前，确认其中的 GUI 和后台已通过正常退出停止。不要用强制结束进程来清理 USB Key 程序。
