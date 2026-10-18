# 第三方软件声明

**简体中文** | [English](docs/THIRD-PARTY-NOTICES.en.md) | [日本語](docs/THIRD-PARTY-NOTICES.ja.md)

aGlass2OSC 的原创代码使用 [MIT License](LICENSE)。第三方组件仍适用各自的版权声明和许可。本文件是来源与许可索引，不替代上游许可全文，也不将第三方组件重新许可为 MIT。

## 1. 运行依赖和可随包分发的组件

版本以当前依赖清单为准；实际构建所用 Python、包版本和文件哈希见便携包中的 `BUILD-MANIFEST.json`。GUI 与 CLI 的具体文件集合不同，例如 CLI 不打包 Tk 图形界面。

| 组件 | 版本／用途 | 许可与来源 |
| --- | --- | --- |
| CPython | Python 3.12 x64；便携包解释器和标准库 | PSF License Agreement 及随 Python 分发的其他许可；[许可说明](https://docs.python.org/3.12/license.html) |
| Tcl / Tk | Python 安装提供的 8.6 系列；GUI | Tcl/Tk 的 BSD 风格许可；各自的 `license.terms` 为准；[Tcl/Tk 许可](https://www.tcl.tk/software/tcltk/license.html) |
| python-osc | 1.10.2；OSC 编码与发送 | The Unlicense；[attwad/python-osc](https://github.com/attwad/python-osc) |
| pyopenvr（Python 包名 `openvr`） | 2.12.1401；OpenVR Python 绑定 | BSD-3-Clause，Christopher Bruns 及贡献者；[cmbruns/pyopenvr](https://github.com/cmbruns/pyopenvr) |
| Valve OpenVR | 上述包携带的 x64 OpenVR API DLL；版本随包而定 | BSD-3-Clause，Valve Corporation；[OpenVR LICENSE](https://github.com/ValveSoftware/openvr/blob/master/LICENSE) |
| usbip（usbip-python） | 0.7.0；虚拟 USB/IP 设备支持 | MIT，Jabez Winston；[jabezwinston/usbip-python](https://github.com/jabezwinston/usbip-python) |
| usbip-win2 | 0.9.8.1 x64；默认随便携包提供的独立驱动安装程序 | BSD-2-Clause，Vadym Hrynchyshyn；[该版本许可](https://github.com/vadimgrn/usbip-win2/blob/v.0.9.8.1/LICENSE.txt) |

usbip-win2 使用未修改的官方安装程序 `USBip-0.9.8.1-x64.exe`，SHA-256：

```text
38cad6d4432b52d5bb9409d9ad03b72fdffc4ada4cd3a48fbeca1a2752a8518a
```

来源：[官方 0.9.8.1 发布页](https://github.com/vadimgrn/usbip-win2/releases/tag/v.0.9.8.1)。驱动 EXE 不进入 Git 源码或最小源码 ZIP；默认构建可以下载并校验它，`--without-driver` 可省略。驱动安装程序自身包含的其他组件仍适用其各自许可。

## 2. 构建工具

| 工具 | 当前版本 | 许可与来源 |
| --- | --- | --- |
| PyInstaller | 6.22.3 | GPL-2.0-or-later，附 Bootloader Exception；部分文件使用 Apache-2.0。以 `COPYING.txt` 为准；[官方许可说明](https://pyinstaller.org/en/stable/license.html) |
| pyinstaller-hooks-contrib | 2026.8 | 普通 hooks／文件为 GPL-2.0-or-later，runtime hooks 为 Apache-2.0；[项目许可](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/LICENSE) |

PyInstaller 的构建工具许可与其打包例外应一并阅读，不能简单地将工具许可视为本项目全部输出的许可。完整条款以对应版本上游文件为准。

## 3. 外部软件与兼容接口

- [aGlassRuntime](https://www.7invensun.com/filedownload/179638)、原厂 SDK、设备与个人校准由用户另行准备；不包含在标准源码或便携包中，其许可由七鑫易维／相应权利人提供。
- [SteamVR / OpenVR](https://github.com/ValveSoftware/openvr)、[VRChat OSC](https://docs.vrchat.com/docs/osc-eye-tracking) 和 [VRCFaceTracking](https://docs.vrcft.io/docs/intro/getting-started) 是本项目对接的外部软件或接口。SteamVR、VRChat 和 VRCFaceTracking 应用程序未随本项目分发。
- [旧 WDM USB/IP 驱动](https://github.com/cezanne/usbip-win)仅作为兼容后端，由用户自行安装；本项目默认分发的是上表的 usbip-win2 安装程序，不能混用两者的许可结论。
- [aGlass VRCFT 模块](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module)独立维护，其源码和模块包不包含在本项目标准发布包中。

`aglass_key.bin` 是项目提供的 202 字节模拟协议应答资源，不是原厂固件或原始磁盘镜像。此处关于文件用途的说明不改变外部 Runtime 或 SDK 的许可。

## 4. 许可文件与归属

构建脚本会将 Python 安装和依赖包中可取得的许可文件收集到便携包的 `licenses/`。该目录属于构建产物，不是源码根目录的一部分。分发时请保留这些文件、安装程序自身的声明以及各组件要求保留的版权信息。Python 或安装程序携带的其他组件，以各自附带的声明为准；本索引不是所有传递依赖的完整清单。

项目中出现的产品名称和商标属于各自权利人，仅用于标识兼容对象和来源，不表示官方授权、合作或背书。三种语言的本文用于说明和索引；若与上游许可原文存在差异，以适用的原文为准。新增或更新依赖时，请同步更新本文件及译文。
