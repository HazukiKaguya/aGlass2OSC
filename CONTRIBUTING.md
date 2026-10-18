# 贡献指南

**简体中文** | [English](docs/CONTRIBUTING.en.md) | [日本語](docs/CONTRIBUTING.ja.md)

欢迎提交错误报告、兼容性验证、代码修复和文档翻译。本项目维护 aGlass2OSC 的 Python 桥接、GUI、CLI 与虚拟 USB Key；VRCFT C# 模块请到 [独立模块项目](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module) 提交相关问题或修改。

## 1. 报告问题

先搜索已有 Issue，提交时尽量提供：

- Windows 版本、aGlass 型号、Runtime 版本，以及 GUI／CLI 包版本或源码提交。
- 连接方式（Runtime 直连或 SDK）、SDK 配置／DLL 文件版本、输出目标及是否运行 SteamVR。
- 可复现步骤、预期结果、实际结果和相关日志；界面问题可附截图。
- USB Key 问题需注明 WDM／usbip-win2 后端、驱动版本及正常停止后的状态。

分享日志前移除个人路径、序列号等不必要的个人信息。不要上传个人校准文件、原始磁盘镜像或无权分发的 SDK。请区分模拟验证和实际佩戴设备的验证结果；眨眼估算不等于原生眼睑开合度。

## 2. 准备开发环境

使用 Windows x64 和 Python 3.12 x64（包含 Tcl/Tk），在项目根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe aglass_gui.py
.\.venv\Scripts\python.exe aglass2vrc.py --help
```

无需设备即可修改界面、运行模拟模式和执行大部分测试。实机验证需自行准备匹配的 [aGlassRuntime](https://www.7invensun.com/filedownload/179638)、硬件和校准数据。目录说明见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

## 3. 验证修改

在包含 `tests/` 的完整开发树中运行回归测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

最小构建源码 ZIP 不包含 `tests/`；不要把缺少测试目录时的零测试结果写成验证通过。无设备的 CLI 检查：

```powershell
.\.venv\Scripts\python.exe aglass2vrc.py --simulate --dry-run --projection fov --duration 3
```

修改打包、依赖或程序入口时，构建并检查受影响的目标：

```powershell
.\build-gui.bat
.\build-cli.bat
```

GUI 包检查会短暂打开窗口；CLI 包检查不打开界面。包检查使用模拟数据，不连接设备或发送 OSC。仅修改文档时，检查相对链接、语言切换和源码打包清单即可。硬件相关修改请说明实际验证过的设备／Runtime 组合及尚未验证的部分。

## 4. 提交 Pull Request

- 每个 PR 聚焦一个问题，描述触发场景、修改后的行为和验证结果。
- 遵循现有代码组织；行为修复按需要补充回归测试，避免无关重构。
- 公共功能或命令改变时，同步中文、英文、日文 README；修改贡献指南或第三方声明时也同步对应译文。
- 新增或升级依赖时更新 `requirements*.txt`、[第三方声明](THIRD-PARTY-NOTICES.md)及必要的打包许可收集。
- 修改分发文件时检查 `tools/package_source.py` 的明确文件清单。使用 `python tools/package_source.py` 检查源码导出。

## 5. 文件与退出约定

不要提交 `.venv/`、`release/`、`tmp/`、`res/archive/`、用户设置、日志或构建缓存。历史研究材料保存在本地归档，不参与标准构建；SDK 查找仍可发现归档中的 DLL。

`aglass_key.bin` 是项目保留的模拟协议应答资源。驱动 EXE 不进入源码仓库；默认构建使用本地官方安装包，缺失时下载并校验。不要为方便测试而修改共享的 Runtime 或驱动状态。

测试 USB Key 后使用“停止 Key”、正常关闭 GUI 或 Ctrl+C，等待 detach。不要强制结束 Key 进程，也不要在未确认旧实例状态时反复启动新实例。

## 6. 许可

提交的原创贡献应可按项目的 [MIT License](LICENSE) 分发。引入第三方内容时保留其版权声明和许可，并注明来源；第三方内容不会因进入本仓库而自动变为 MIT。详见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。
