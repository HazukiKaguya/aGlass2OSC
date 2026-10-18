# Windows GUI 便携版

**简体中文** | [English](WINDOWS_EXE.en.md) | [日本語](WINDOWS_EXE.ja.md)

完整解压 `aGlass2OSC-Windows-x64-gui.zip`，运行 `aGlass2OSC.exe`。请保留整个目录，后台 EXE 与 `_internal` 缺一不可。无需安装 Python、pip 或 Windows App SDK。

默认包保留四页 GUI、OSC/OpenVR/USB Key 的 Python 依赖、协议资源、许可和校验清单。包含 `drivers/USBip-0.9.8.1-x64.exe` 和程序旁的 `aglass_key.bin` 模拟应答文件；不带厂商 SDK、Runtime、磁盘镜像或 VRCFT 模块 ZIP。VRCFT 模块从 [独立项目](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module) 获取。

Runtime 下载：[aGlassRuntime](https://www.7invensun.com/filedownload/179638)。实际连接设备前请安装配套 Runtime 并完成个人校准。

使用自己的可写目录，设置保存为 `aglass-gui.json`。升级前正常停止旧版，按需迁移自己的设置。可先用“模拟预览”确认 GUI 和后台协作，再接入配套设备与 Runtime。桌面投影无需 SteamVR。

GUI 有四个页面：连接与输出、眼动设置、高级设置、虚拟 USB Key。内容放得下时隐藏滚动条；收起的下拉选单不会被滚轮切换。眨眼来自有效性估算，无法代替原生眼睑开合度。

首次使用虚拟 Key 时，如尚未安装 usbip-win2，请手动运行包内 `drivers/USBip-0.9.8.1-x64.exe`；安装需要管理员权限，可能要求重启。Key 应答路径留空时优先使用程序旁的 `aglass_key.bin`。停止时用“停止 Key”、正常关窗或 Ctrl+C；不要强制结束后台。GUI 不自动安装驱动。眼动硬件、校准和授权仍需在 Runtime 中正常工作。

无需硬件的自检：

```powershell
.\aGlass2OSC-worker.exe --self-test
.\aGlass2OSC-worker.exe --cli --simulate --dry-run --projection fov --duration 1
```

GUI 自检可使用 `aGlass2OSC.exe --self-test report.json`，会短暂显示窗口、运行模拟预览、正常停止后台并将结果写入指定文件，不连接真实眼动设备或创建虚拟 USB 设备。

构建方式见[根目录 README](../README.md)。EXE 未做代码签名；`BUILD-MANIFEST.json` 保存打包依赖版本与文件 SHA-256，ZIP 旁另有整体校验文件。

组件来源与许可见[第三方软件声明](../THIRD-PARTY-NOTICES.md)。
