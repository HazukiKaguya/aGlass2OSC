# コントリビューションガイド

[简体中文](../CONTRIBUTING.md) | [English](CONTRIBUTING.en.md) | **日本語**

不具合報告、互換性の検証、修正、翻訳を歓迎します。本プロジェクトでは aGlass2OSC の Python ブリッジ、GUI、CLI、仮想 USB Key を管理しています。VRCFT の C# モジュールに関する問題や変更は、[独立したモジュールのリポジトリ](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module)へお願いします。

## 1. 問題を報告する

既存の Issue を確認し、可能な範囲で次の情報を記載してください。

- Windows のバージョン、aGlass の機種、Runtime のバージョン、GUI／CLI のリリースまたはソースのコミット。
- 接続方式（Runtime 直接接続／SDK）、SDK プロファイルや DLL のファイルバージョン、出力先、SteamVR の起動状況。
- 再現手順、期待する動作、実際の動作、関連ログ。UI の問題にはスクリーンショットも役立ちます。
- USB Key の問題では、WDM／usbip-win2 の選択、ドライバーバージョン、正常終了後の状態。

ログを共有する前に、不要な個人パスやシリアル番号などを削除してください。個人のキャリブレーションデータ、ディスクの生イメージ、再配布できない SDK はアップロードしないでください。シミュレーションと実際に装着した状態での検証を区別してください。まばたき推定は、実測のまぶた開度ではありません。

## 2. 開発環境を準備する

Windows x64 と Tcl/Tk を含む Python 3.12 x64 を使用し、プロジェクトのルートで実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe aglass_gui.py
.\.venv\Scripts\python.exe aglass2vrc.py --help
```

UI の変更、シミュレーション、多くのテストは実機なしで行えます。実機検証には、対応する [aGlassRuntime](https://www.7invensun.com/filedownload/179638)、ハードウェア、キャリブレーションデータが必要です。ディレクトリ構成は [DEVELOPMENT.md](DEVELOPMENT.md)（中国語）を参照してください。

## 3. 変更を検証する

`tests/` を含む完全な開発ツリーでは、次を実行します。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

最小ビルド用ソース ZIP に `tests/` は含まれません。ディレクトリがないためテストが 0 件だった場合、検証済みとは記載しないでください。実機を使わない CLI の確認方法：

```powershell
.\.venv\Scripts\python.exe aglass2vrc.py --simulate --dry-run --projection fov --duration 3
```

パッケージ処理、依存関係、起動処理を変更した場合は、影響する対象をビルドして検証します。

```powershell
.\build-gui.bat
.\build-cli.bat
```

GUI パッケージの検証ではウィンドウが一時的に表示されます。CLI の検証では表示されません。パッケージ検証は模擬データを使用し、実機への接続や OSC 送信は行いません。文書のみの変更では、相対リンク、言語切り替え、ソースの梱包リストを確認してください。実機関連の変更では、検証した機種／Runtime の組み合わせと未検証の範囲を明記してください。

## 4. Pull Request を送る

- 1 つの PR は 1 つの問題に絞り、発生条件、変更後の動作、検証結果を説明してください。
- 既存のコード構成に合わせ、動作修正には必要に応じて回帰テストを追加してください。無関係なリファクタリングは避けてください。
- 公開機能やコマンドを変更した場合は、中・英・日 README を同期してください。貢献ガイドや第三者ソフトウェアの表記を変更した場合も、対応する翻訳を更新してください。
- 依存関係の追加や更新では、`requirements*.txt`、[第三者ソフトウェアに関する表記](THIRD-PARTY-NOTICES.ja.md)、必要なライセンス収集処理も更新してください。
- 配布ファイルを変更した場合は `tools/package_source.py` の明示的なリストを確認し、`python tools/package_source.py` でソース出力を確認してください。

## 5. ファイルと終了処理

`.venv/`、`release/`、`tmp/`、`res/archive/`、個人設定、ログ、ビルドキャッシュはコミットしないでください。過去の調査資料はローカルのアーカイブに保存し、標準ビルドに含めません。SDK の自動検索ではアーカイブ内の DLL も検出できます。

`aglass_key.bin` はプロジェクトに含める模擬プロトコル応答データです。ドライバー EXE はソースリポジトリに含めません。通常のビルドはローカルの公式インストーラーを使用し、ない場合はダウンロードして検証します。テストの都合だけで共有の Runtime やドライバーの状態を変更しないでください。

USB Key の検証後は、Key の停止、GUI の通常終了、または Ctrl+C を使い、detach の完了を待ってください。Key プロセスを強制終了したり、前のインスタンスの状態を確認せずに繰り返し起動したりしないでください。

## 6. ライセンス

独自の貢献は、プロジェクトの [MIT License](../LICENSE) で配布できる内容にしてください。第三者のコードや資料を含める場合は、著作権表示とライセンスを保持し、出典を明記してください。本リポジトリへの追加によって第三者のコンテンツが MIT に変更されるわけではありません。[THIRD-PARTY-NOTICES.ja.md](THIRD-PARTY-NOTICES.ja.md) も参照してください。
