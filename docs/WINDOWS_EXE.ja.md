# Windows GUI ポータブル版

[简体中文](WINDOWS_EXE.md) | [English](WINDOWS_EXE.en.md) | **日本語**

`aGlass2OSC-Windows-x64-gui.zip` を完全に展開し、`aGlass2OSC.exe` を起動してください。バックグラウンド用 EXE と `_internal/` を含め、フォルダー全体を保持してください。Python、pip、Windows App SDK のインストールは不要です。

通常のパッケージには、4 ページの GUI、OSC／OpenVR／USB Key 用の Python 依存関係、プロトコルリソース、ライセンス、チェックサム一覧が含まれます。`drivers/USBip-0.9.8.1-x64.exe` と、アプリの隣の模擬応答ファイル `aglass_key.bin` を同梱しています。メーカー SDK、Runtime、ディスクイメージ、VRCFT モジュール ZIP は含みません。VRCFT モジュールは [独立したプロジェクト](https://github.com/HazukiKaguya/HTC-Vive-7invensun-aGlass-Module)から取得してください。

Runtime のダウンロード：[aGlassRuntime](https://www.7invensun.com/filedownload/179638)。実機利用の前に、対応する Runtime をインストールして個人のキャリブレーションを完了してください。

書き込み可能なフォルダーを使用してください。設定は `aglass-gui.json` に保存されます。更新前に旧版を正常終了し、必要に応じて設定を移行してください。まずシミュレーションプレビューで GUI とバックグラウンド処理の連携を確認し、その後に実機と Runtime を使用できます。デスクトップ FOV 投影に SteamVR は不要です。

GUI には、接続と出力、視線設定、詳細設定、仮想 USB Key の 4 ページがあります。内容が収まる場合はスクロールバーを隠し、閉じたドロップダウンはホイールで変更されません。まばたきはデータの有効性からの推定であり、実測のまぶた開度ではありません。

仮想 Key の初回使用時、usbip-win2 が未導入なら `drivers/USBip-0.9.8.1-x64.exe` を手動実行してください。管理者権限と再起動が必要になる場合があります。応答ファイルのパスが空の場合は、アプリの隣の `aglass_key.bin` を優先します。停止には Key 停止、通常のウィンドウ終了、または Ctrl+C を使い、バックグラウンドプロセスを強制終了しないでください。GUI はドライバーを自動インストールしません。ハードウェア、キャリブレーション、認証が Runtime で正常に動作している必要があります。

実機を使わない自己診断：

```powershell
.\aGlass2OSC-worker.exe --self-test
.\aGlass2OSC-worker.exe --cli --simulate --dry-run --projection fov --duration 1
```

GUI の自己診断は `aGlass2OSC.exe --self-test report.json` で実行できます。ウィンドウを一時的に表示し、シミュレーションプレビューを実行してバックグラウンド処理を正常停止し、結果を指定ファイルへ書き込みます。実機への接続や仮想 USB デバイスの作成は行いません。

ビルド方法は [日本語 README](README.ja.md) を参照してください。EXE はコード署名されていません。`BUILD-MANIFEST.json` に依存バージョンと各ファイルの SHA-256 を記録し、ZIP 全体のチェックサムも別途用意しています。出典とライセンスは [第三者ソフトウェアに関する表記](THIRD-PARTY-NOTICES.ja.md)を参照してください。
