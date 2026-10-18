# aGlass2OSC

[简体中文](../README.md) | [English](README.en.md) | **日本語**

aGlass2OSC は、7invensun（七鑫易維）aGlass の視線データを VRChat（OSC）または VRCFaceTracking に送信する Windows 用ブリッジツールです。GUI と独立した CLI を備え、起動済みの aGlass Runtime 1.1 への直接接続や、対応する SDK を利用した接続に対応し、仮想 USB Key の管理機能も提供します。

Windows 向けポータブル版には必要な実行環境が含まれており、Python や Python パッケージを別途インストールする必要はありません。

**Runtime のダウンロード：[aGlassRuntime](https://www.7invensun.com/filedownload/179638)**。実機を使う前に、対応する Runtime をインストールしてキャリブレーションを完了してください。Runtime は本プロジェクトの配布パッケージに含まれません。

## 機能紹介

### 1. 視線追跡と VRChat 出力

- VRChat 標準の OSC 視線出力に対応。統合した視線、またはデータソースが対応する場合は左右独立した視線を出力できます。
- まばたき推定は既定で有効です。必要に応じて無効にできます。
- 視線の平滑化、中心位置の補正、水平／垂直ゲイン、軸の反転を調整できます。
- 古いデータを判定し、追跡が途切れた後に過去の視線を送り続けることを防ぎます。
- 投影方式の自動選択、デスクトップ FOV、SteamVR 投影の明示的な選択に対応。デスクトップ利用で SteamVR の起動は必須ではありません。

### 2. Runtime と SDK の互換性

- **Runtime 1.1 直接接続**では、ローカル通信で既存の Runtime を利用します。SDK DLL を読み込まず、別の Runtime を起動しません。
- SDK モードでは、起動中の Runtime に対応する DLL を選択できます。DK I / vi-1 の異なる API バージョンや DK II 向けの設定を用意しています。
- DLL の自動検索、API の識別、手動指定、診断に対応しています。
- SDK は既定で独立した子プロセスで動作し、起動・終了のタイムアウトを備えます。ネイティブ SDK のクラッシュや停止がブリッジへ与える影響を抑えます。

### 3. グラフィカルインターフェース

Tk/ttk で実装した **WinUI 3 / Fluent 風の GUI** です。Windows App SDK は不要です。

| ページ | 機能 |
| --- | --- |
| 接続と出力 | Runtime／SDK と出力先を選び、ブリッジを開始・停止 |
| 視線設定 | 視線マッピング、平滑化、まばたき推定を調整 |
| 詳細設定 | 接続パラメーター、診断、ログを設定 |
| 仮想 USB Key | ドライバーの状態を確認し、Key を開始・停止 |

動作状態、OSC パケット数、経過時間、ログを表示し、設定の保存・再読み込みに対応しています。**シミュレーションプレビュー**では実機への接続や OSC 送信を行わずに視線表示を確認できます。

起動、ページ切り替え、レイアウトの応答性を改善しています。操作ボタンと状態表示をまとめ、設定欄の表示領域を広げています。閉じたドロップダウンの値はマウスホイールで変更されません。内容がすべて収まる場合はスクロールバーを隠し、不要なページスクロールを行いません。

### 4. 仮想 USB Key

- GUI で管理でき、CLI からも起動できます。
- 従来の WDM ドライバーと usbip-win2 に対応し、バックエンドを自動選択または手動指定できます。
- 正常終了時に detach し、異常終了後の状態確認と復旧記録を行います。旧ドライバーのポート解放を確認できない場合、追加のスロット消費を防ぎます。
- ポータブル版に公式 **usbip-win2 0.9.8.1 x64** インストーラーを同梱しています。必要な場合に手動でインストールします。
- 模擬プロトコル応答ファイル `aglass_key.bin` を同梱しています。アプリの隣の BIN を優先し、ない場合は内蔵リソースを使用します。

終了時は GUI の Key 停止、通常のウィンドウ終了、または Ctrl+C を使用し、後処理を完了させてください。プロセスの強制終了ではドライバーのリソースが残る場合があります。

### 5. VRCFaceTracking への対応

aGlass VRCFT モジュールへのブリッジデータ送信と、VRCFT Avatar パラメーターの直接出力に対応しています。モジュールのソース、ビルド、インストール用パッケージは [HTC-Vive-7invensun-aGlass-Module](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module) で個別に管理しています。

モジュールが Runtime に直接接続する場合、aGlass2OSC の視線ブリッジは不要です。モジュールのブリッジモードを使う場合は `Source=bridge` に設定してください。

### 6. GUI／CLI ポータブル版

Windows x64 向けに、実行時依存関係を含む 2 種類のパッケージを提供します。Python のインストールは不要です。

| ファイル | 用途 |
| --- | --- |
| `aGlass2OSC-Windows-x64-gui.zip` | 展開して `aGlass2OSC.exe` を起動 |
| `aGlass2OSC-Windows-x64-cli.zip` | 展開して端末から `aGlass2OSC-cli.exe` を実行 |
| `aGlass2OSC-GitHub-source.zip` | GUI／CLI のビルドに必要な最小ソースパッケージ |
| `*.zip.sha256` | 対応する ZIP の SHA-256 チェックサム |

パッケージ全体を展開し、`_internal/` などの付属ファイルを保持してください。CLI は視線ブリッジと `--key` サブコマンドに対応しています。Key が起動済みの場合、重複して起動する必要はありません。

### 7. ソースとビルド

- Python CLI の起動ファイル `aglass2vrc.py` と、`run-gui.bat`／`run-cli.bat` を提供しています。
- `build-gui.bat` または `build-cli.bat` で、それぞれのパッケージをビルド・検証できます。キャッシュと出力先は別々です。
- 配布パッケージには依存ソフトウェアのライセンス、ファイルの検証一覧、ZIP の SHA-256 を含みます。
- 最小ソースパッケージには模擬応答 BIN を含め、ドライバーインストーラー、メーカー SDK、過去のアーカイブは含めません。
- ドライバー EXE は Git の除外設定と `export-ignore` で除外しています。通常のビルドでは、ローカルにない場合に固定バージョンの公式インストーラーをダウンロードし、SHA-256 を検証します。

**対応範囲：**まばたきは目／視線データの有効性からの推定であり、連続的なまぶた開度の実測ではありません。機種と Runtime に対応する SDK 設定を使用してください。設定の存在はすべての組み合わせでの実機検証を意味しません。aGlass Runtime、メーカー SDK、ハードウェア、個人のキャリブレーションは別途準備してください。

## Windows GUI を使う

**aGlass2OSC-Windows-x64-gui.zip** を完全に展開し、`aGlass2OSC.exe` を実行します。同じフォルダーの `aGlass2OSC-worker.exe` と `_internal/` を保持してください。設定は EXE の隣の `aglass-gui.json` に保存されます。

1. 最初にシミュレーションプレビューで表示を確認できます。実機への接続や OSC 送信は行いません。
2. 実機利用では対応する Runtime を起動し、デバイス認証の準備と個人のキャリブレーションを完了してください。
3. Runtime 1.1 直接接続を選ぶと、DLL を読み込まず既存 Runtime と通信します。その他の Runtime や DK II では、対応する SDK プロファイルと x64 DLL を指定します。
4. VRChat 標準出力を選び、VRChat の OSC を有効にしてください。デスクトップでは自動投影またはデスクトップ FOV を使えます。SteamVR 投影を明示的に選ぶ場合は SteamVR が必要です。
5. ブリッジを開始し、有効な視線データと出力を確認してください。停止後、必要に応じて設定を保存します。

## Windows CLI を使う

**aGlass2OSC-Windows-x64-cli.zip** を完全に展開し、`_internal/` などを保持したまま、そのフォルダーで端末を開きます。

```powershell
.\aGlass2OSC-cli.exe --help
.\aGlass2OSC-cli.exe --simulate --dry-run --projection fov --duration 3
```

2 行目は模擬データのみを処理し、実機への接続や OSC 送信は行いません。起動済みの Runtime 1.1 に接続する例：

```powershell
.\aGlass2OSC-cli.exe --connection runtime --projection fov
```

Key のコマンドは `--key --help` で確認できます。詳しくは [CLI の説明](CLI.ja.md)を参照してください。

## GUI パッケージをビルドする

**Windows x64、Tcl/Tk を含む Python 3.12 x64** と、依存パッケージをダウンロードできるネットワーク環境が必要です。.NET SDK、VRCFT モジュールのプロジェクト、メーカー DLL、Runtime インストーラーはビルドに不要です。ドライバーインストーラーもビルド時に取得できます。専用の仮想環境を使ってください。

ソースのルートで実行します。

```powershell
.\build-gui.bat
```

`.venv` の作成、固定バージョンの依存関係のインストール、2 つの EXE のビルド、実機を使わないパッケージ検証を行います。検証中は GUI が一時的に表示されます。各手順を個別に実行する場合：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/build_exe.py --target gui
.\.venv\Scripts\python.exe tools/check_exe.py --target gui
```

出力ファイル：

```text
release/aGlass2OSC-Windows-x64-gui.zip
release/aGlass2OSC-Windows-x64-gui.zip.sha256
```

ビルドごとに新しい `release/build-*` を使用し、実行中の可能性がある古いプログラムを削除しません。ZIP には EXE、共有実行環境、説明書、ライセンス、チェックサム一覧が含まれます。既定では `drivers/USBip-0.9.8.1-x64.exe` と `aglass_key.bin` を同梱します。ドライバーはローカルのものを優先し、ない場合は固定バージョンをダウンロードして SHA-256 を検証します。`--driver-installer` で既存ファイルを指定でき、`--without-driver` で同梱を省略できます。ビルド処理はドライバーをインストールしません。

依存関係の準備後、ソースから GUI を起動するには `.\.venv\Scripts\python.exe aglass_gui.py` または `run-gui.bat` を使用します。

## CLI パッケージをビルドする

GUI と同じ **Windows x64、Python 3.12 x64** の環境と、依存関係のダウンロード環境を使用します。

```powershell
.\build-cli.bat
```

`.venv` の作成、依存関係のインストール、独立した `aGlass2OSC-cli.exe` のビルド、実機を使わない検証を行います。CLI の検証では GUI は開きません。個別に実行する場合：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/build_exe.py --target cli
.\.venv\Scripts\python.exe tools/check_exe.py --target cli
```

出力ファイル：

```text
release/aGlass2OSC-Windows-x64-cli.zip
release/aGlass2OSC-Windows-x64-cli.zip.sha256
```

CLI パッケージにも実行時依存関係、公式ドライバーインストーラー、`aglass_key.bin` を含みます。`--driver-installer` と `--without-driver` も利用できます。GUI と CLI のビルドキャッシュと出力先は別々です。

ソースからは `.\.venv\Scripts\python.exe aglass2vrc.py --help` または `run-cli.bat --help` を使用します。ソース ZIP には両方のビルド用ファイルが含まれます。

## VRCFaceTracking

**モジュールのソース、ビルド、インストール用パッケージは別管理です：**
[HTC-Vive-7invensun-aGlass-Module](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module)

本リポジトリでは C# モジュールのビルドや同梱は行いません。GUI はモジュールへのブリッジ出力と、VRCFT Avatar パラメーターの直接出力に対応しています。モジュールが Runtime に直接接続する場合は GUI の視線ブリッジは不要です。`Source=bridge` の場合は GUI で VRCFT モジュール出力を選びます。既定のポートは 9015 です。同じ Runtime を複数のクライアントで同時に制御しないでください。

## 仮想 USB Key と終了方法

usbip-win2 と従来の WDM ドライバーに対応しています。GUI／CLI パッケージには公式インストーラーを同梱しています。未導入の場合は `drivers/USBip-0.9.8.1-x64.exe` を手動で実行してください。管理者権限と再起動が必要になる場合があります。GUI が自動的にドライバーをインストールすることはありません。

`aglass_key.bin` は 202 バイトの模擬プロトコル応答ファイルであり、ファームウェアイメージではありません。ソースと GUI／CLI パッケージに含まれます。応答ファイルのパスが空の場合はアプリの隣の BIN を優先し、なければ `aglass_vrc/key_protocol.json` にフォールバックします。別の応答ファイルを指定することもできます。元のディスクイメージ、メーカー SDK、個人のキャリブレーションデータは含まれません。

GUI の Key 停止、通常の終了、または Ctrl+C を使用し、detach を完了させてください。Key バックグラウンドプロセスを強制終了しないでください。旧ドライバーの異常終了後の復旧用に `tools/recover_vhci.ps1` があります。実行前にスクリプトの説明と影響範囲を確認してください。

## ソースの公開と ZIP の生成

開発構成と作業手順は [DEVELOPMENT.md](DEVELOPMENT.md)（中国語）を参照してください。過去の資料は `res/archive/` に保存し、ビルドやソースパッケージに含めません。SDK の自動検索ではアーカイブ内の DLL も検出できます。

GUI／CLI に必要な Python モジュール、プロトコルリソース、起動ファイル、依存リスト、ツール、説明書を保持しています。ドライバー EXE は `.gitignore` と `export-ignore` で除外し、`aglass_key.bin` は明示的に残します。`release/`、キャッシュ、個人設定、ログは Git から除外します。実行ファイルのパッケージは GitHub Release の添付ファイルとして公開します。

```powershell
python tools/package_source.py
```

明示的なファイルリストから `release/aGlass2OSC-GitHub-source.zip` と SHA-256 を生成します。模擬応答 BIN を含み、ドライバーインストーラーを除外します。SDK、ディスクイメージ、キャッシュ、ログを作業フォルダーから再帰的に集めることはありません。ソース ZIP を展開し、その `aGlass2OSC/` の内容をリポジトリのルートとして使用してください。GUI の説明は [WINDOWS_EXE.ja.md](WINDOWS_EXE.ja.md) を参照してください。

## 貢献と第三者ソフトウェア

不具合報告や変更の提出については [貢献ガイド](CONTRIBUTING.ja.md)を、依存ソフトウェアの出典とライセンスについては [第三者ソフトウェアに関する表記](THIRD-PARTY-NOTICES.ja.md)を参照してください。

## ライセンス

本プロジェクトは [MIT License](../LICENSE) で公開しています。ビルドには Python、Tk、python-osc、OpenVR、usbip、パッケージ化ツールのライセンス文書を含めます。aGlass Runtime、メーカー SDK、ハードウェアは別途準備してください。第三者製ドライバーのインストーラーは GUI／CLI に同梱します。本プロジェクトはコミュニティによるツールです。
