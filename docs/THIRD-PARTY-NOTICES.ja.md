# 第三者ソフトウェアに関する表記

[简体中文](../THIRD-PARTY-NOTICES.md) | [English](THIRD-PARTY-NOTICES.en.md) | **日本語**

aGlass2OSC の独自コードは [MIT License](../LICENSE) で公開しています。第三者のコンポーネントには、それぞれの著作権表示とライセンスが適用されます。この文書は出典とライセンスの索引であり、上流のライセンス全文を置き換えたり、第三者のコンポーネントを MIT に変更したりするものではありません。

## 1. 実行時依存関係と同梱される場合があるコンポーネント

以下のバージョンは現在の依存リストに対応します。実際の Python、パッケージのバージョン、ファイルハッシュは、ポータブル版の `BUILD-MANIFEST.json` を確認してください。GUI と CLI では内容が異なり、例えば CLI は Tk の GUI を同梱しません。

| コンポーネント | バージョン／用途 | ライセンスと出典 |
| --- | --- | --- |
| CPython | Python 3.12 x64；実行環境と標準ライブラリ | PSF License Agreement および Python に付属するその他のライセンス；[ライセンス文書](https://docs.python.org/3.12/license.html) |
| Tcl / Tk | Python に付属する 8.6 系列；GUI | Tcl/Tk の BSD 系の条項。各 `license.terms` を参照；[Tcl/Tk ライセンス](https://www.tcl.tk/software/tcltk/license.html) |
| python-osc | 1.10.2；OSC の生成と送信 | The Unlicense；[attwad/python-osc](https://github.com/attwad/python-osc) |
| pyopenvr（Python パッケージ名 `openvr`） | 2.12.1401；OpenVR Python バインディング | BSD-3-Clause、Christopher Bruns および貢献者；[cmbruns/pyopenvr](https://github.com/cmbruns/pyopenvr) |
| Valve OpenVR | 上記パッケージに付属する x64 OpenVR API DLL。バージョンはその配布物に依存 | BSD-3-Clause、Valve Corporation；[OpenVR LICENSE](https://github.com/ValveSoftware/openvr/blob/master/LICENSE) |
| usbip（usbip-python） | 0.7.0；仮想 USB/IP デバイス | MIT、Jabez Winston；[jabezwinston/usbip-python](https://github.com/jabezwinston/usbip-python) |
| usbip-win2 | 0.9.8.1 x64；既定で同梱する独立したドライバーインストーラー | BSD-2-Clause、Vadym Hrynchyshyn；[該当バージョンのライセンス](https://github.com/vadimgrn/usbip-win2/blob/v.0.9.8.1/LICENSE.txt) |

改変していない公式 usbip-win2 インストーラー `USBip-0.9.8.1-x64.exe` を使用します。SHA-256：

```text
38cad6d4432b52d5bb9409d9ad03b72fdffc4ada4cd3a48fbeca1a2752a8518a
```

出典：[公式 0.9.8.1 リリース](https://github.com/vadimgrn/usbip-win2/releases/tag/v.0.9.8.1)。ドライバー EXE は Git のソースと最小ソース ZIP に含めません。通常のビルドではダウンロードと検証を行えます。`--without-driver` で同梱を省略できます。インストーラー内のその他のコンポーネントには、それぞれのライセンスが適用されます。

## 2. ビルドツール

| ツール | 現在のバージョン | ライセンスと出典 |
| --- | --- | --- |
| PyInstaller | 6.22.3 | GPL-2.0-or-later と Bootloader Exception。一部ファイルは Apache-2.0。`COPYING.txt` と [公式の説明](https://pyinstaller.org/en/stable/license.html)を参照 |
| pyinstaller-hooks-contrib | 2026.8 | 通常の hooks／ファイルは GPL-2.0-or-later、runtime hooks は Apache-2.0；[プロジェクトのライセンス](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/LICENSE) |

PyInstaller のツール本体のライセンスとパッケージ化に関する例外は、併せて確認してください。ツールのライセンスだけで本プロジェクトのすべての出力物のライセンスが決まるわけではありません。完全な条項は該当バージョンの上流ファイルを参照してください。

## 3. 外部ソフトウェアと互換インターフェース

- [aGlassRuntime](https://www.7invensun.com/filedownload/179638)、メーカー SDK、デバイス、個人のキャリブレーションは別途準備してください。標準ソースやポータブル版には含まれず、7invensun または各権利者の条件が適用されます。
- [SteamVR / OpenVR](https://github.com/ValveSoftware/openvr)、[VRChat OSC](https://docs.vrchat.com/docs/osc-eye-tracking)、[VRCFaceTracking](https://docs.vrcft.io/docs/intro/getting-started) は接続先となる外部ソフトウェアまたはインターフェースです。SteamVR、VRChat、VRCFaceTracking のアプリ本体は配布しません。
- [従来の WDM USB/IP ドライバー](https://github.com/cezanne/usbip-win)は互換バックエンドとして、ユーザーが別途インストールするものです。既定で同梱するのは上表の usbip-win2 であり、両者のライセンスを混同しないでください。
- [aGlass VRCFT モジュール](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module)は別管理であり、そのソースやモジュールパッケージは aGlass2OSC の標準配布物に含まれません。

`aglass_key.bin` はプロジェクトが提供する 202 バイトの模擬プロトコル応答データであり、メーカーのファームウェアやディスクの生イメージではありません。この説明は外部 Runtime や SDK のライセンスを変更するものではありません。

## 4. ライセンスファイルと帰属

ビルド処理は、Python 環境と依存パッケージから取得できるライセンスファイルを、ポータブル版の `licenses/` に収集します。このディレクトリはビルド成果物に含まれるもので、ソースのルートにはありません。再配布時はこれらのファイル、インストーラー内の表記、各コンポーネントが要求する著作権表示を保持してください。Python やインストーラーに付属するその他のコンポーネントには、各自の表記が適用されます。この索引はすべての間接依存関係を網羅するものではありません。

製品名と商標は各権利者に帰属し、互換対象や出典を示すために使用しています。公式の認可、提携、推奨を意味しません。本文の三言語版は説明と参照用です。上流のライセンス原文と相違がある場合は、適用される原文に従ってください。依存関係を追加・更新した際は、本文と翻訳も更新してください。
