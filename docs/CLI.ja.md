# Windows CLI の使用方法とビルド

[简体中文](CLI.md) | [English](CLI.en.md) | **日本語**

CLI は GUI と同じブリッジ実装を使用し、Runtime 直接接続、SDK 設定、VRChat OSC、VRCFT 出力、まばたき推定に対応しています。ポータブル版 CLI は GUI を開かず、Python のインストールも不要です。

## ポータブル EXE を使う

`aGlass2OSC-Windows-x64-cli.zip` を完全に展開し、`_internal/` と `aglass_key.bin` を保持したまま、そのフォルダーで端末を開きます。

```powershell
.\aGlass2OSC-cli.exe --help
.\aGlass2OSC-cli.exe --list-profiles
.\aGlass2OSC-cli.exe --simulate --dry-run --projection fov --duration 3
```

最後のコマンドは模擬データのみを処理し、OSC 送信や実機への接続は行いません。`--self-test` では実機を使わず、パッケージの依存関係、Key 応答、子プロセスの起動を確認できます。

実機利用では、対応する [aGlassRuntime](https://www.7invensun.com/filedownload/179638) を用意して起動し、デバイス認証の準備とキャリブレーションを済ませ、VRChat の OSC を有効にします。

```powershell
.\aGlass2OSC-cli.exe --connection runtime --projection fov
```

既存の Runtime 1.1 に直接接続します。デスクトップ FOV に SteamVR は不要です。投影オプションを省略すると `auto` となり、SteamVR の投影を取得できない場合は FOV にフォールバックします。その他の Runtime では `--profile` と `--dll` で対応する SDK を指定できます。`--list-dlls` はインストール先と `res/` 以下（ローカルアーカイブを含む）の DLL 候補を表示します。メーカー SDK は同梱しません。

既定の出力先は VRChat 標準 OSC、ポートは 9000 です。`--target vrcft-module` は独立モジュールのブリッジポートへ出力します。モジュールを `Source=bridge` に設定してください。連続的なまぶた開度は実装されておらず、既定のまばたき出力は有効性からの推定です。

## 仮想 USB Key

CLI パッケージにも公式ドライバーインストーラーと模擬応答 BIN を同梱しています。仮想 Key が必要な場合は別の端末で実行します。

```powershell
.\aGlass2OSC-cli.exe --key --help
.\aGlass2OSC-cli.exe --key --backend auto
```

初回利用時、必要に応じて `drivers/USBip-0.9.8.1-x64.exe` を手動インストールしてください。管理者権限と再起動が必要になる場合があります。複数の Key を同時起動しないでください。GUI の Key が既に動作している場合は、そのまま使用できます。Ctrl+C で正常終了し、detach を完了させてください。ブリッジと Key は別のコマンドであり、ブリッジを終了しても別の端末の Key は停止しません。

## ソースから実行・ビルドする

ソースのルートで実行します。

```powershell
python -m pip install -r requirements.txt -r requirements-usbkey.txt
python aglass2vrc.py --help
.\run-cli.bat --simulate --dry-run --projection fov --duration 3
```

`run-cli.bat` はプロジェクトの `.venv` を優先し、なければ PATH の Python を使用します。コマンドライン引数と終了コードを引き継ぎます。

Windows x64 と Python 3.12 x64 でビルドします。

```powershell
.\build-cli.bat
```

スクリプトは固定バージョンの依存関係をインストールし、次の処理を実行します。環境の準備が済んでいれば個別に実行できます。

```powershell
.\.venv\Scripts\python.exe tools/build_exe.py --target cli
.\.venv\Scripts\python.exe tools/check_exe.py --target cli
```

出力は `release/aGlass2OSC-Windows-x64-cli.zip` と `.zip.sha256` です。GUI と CLI のキャッシュと出力先は別々です。既定ではドライバーを同梱し、`--without-driver` で省略できます。`python tools/package_source.py` は両方のビルド用ファイルを含むソース ZIP を生成し、ドライバーインストーラーは含めません。

[日本語 README](README.ja.md)、[貢献ガイド](CONTRIBUTING.ja.md)、[第三者ソフトウェアに関する表記](THIRD-PARTY-NOTICES.ja.md)も参照してください。
