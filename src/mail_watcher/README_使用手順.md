📘 mail_watcher 使用手順マニュアル
🧩 プロジェクト概要

mail_watcher は、
Amazon・メルカリShops・ラクマ など複数モール間で販売している商品の
在庫を自動同期 するための Python システムです。

メールをIMAP経由で取得し、SKU（商品管理番号）を解析、
それに応じて自動的に在庫数を調整します。

🧠 構成（主要フォルダ）
mail_watcher/
├─ config/            ← 設定ファイル（config.csv）
├─ data/              ← SQLite DB（app.db）が生成される
├─ logs/              ← 各種ログ（extract.log など）
├─ src/
│   └─ mail_watcher/
│       ├─ main_controller.py       ← 🧠 本体スクリプト（対話式）
│       ├─ parsing/extractor.py     ← SKU抽出
│       ├─ services/fetch_service_imap.py  ← メール受信
│       ├─ services/decrease_stock_auto.py ← 在庫同期・Selenium操作
│       ├─ db/init_db.py            ← DB初期化
│       └─ tools/show_db.py         ← DB確認ツール

⚙️ 実行環境

Python 3.11

Chrome + ChromeDriver 必須（Seleniumで使用）

Windows 10/11 推奨

🚀 実行手順
1️⃣ mail_watcherを起動

コマンドプロンプトで以下を実行：

cd "C:\Users\daiji\AppData\Local\Programs\Python\Python311\mail_watcher\src"
python -m mail_watcher.main_controller

2️⃣ DB初期化 + メール受信

最初に、過去 2週間分の受注メール を取得してDB化します。

重複を避けるため、既存の app.db は初期化されます。

3️⃣ メルカリshopsログインプロファイル作成

初回のみ 必要です。

すべてのChromeを閉じた状態で、
プロンプトの案内に従って Enter を押すと Chrome が起動します。

メルカリShopsのログインページが開くので、手動でログインしてください。

ログイン後にChromeを閉じると、
chrome_profiles/mercari/ にログイン済みプロファイルが保存されます。

以降は自動ログインされるため、この手順は不要になります。

4️⃣ 受注処理開始時刻を入力
年：2025
月：11
日：3
時(0～24)：9
分(0～59)：30


この時刻より前のメールは全て「処理済み」にします。
すべて 0 を入力すると、過去2週間分をすべて処理済みに設定します。

5️⃣ SKU抽出・同期処理

Amazon 受注 → メルカリ在庫減少

メルカリ受注 → Amazon在庫減少

ラクマはログのみ記録（同期対象外）

結果は logs/extract.log に記録されます。

6️⃣ 常駐モード

3分ごとに自動で新着メールをチェックします。

Ctrl + C で安全に停止できます。

2025-11-03 14:12:00 | チェック開始...
2025-11-03 14:12:03 | SKU抽出成功 (2件)
2025-11-03 14:12:03 | 同期処理完了

🧾 トラブルシューティング
症状	原因	対応
IMAP接続失敗	メールサーバー名やポート誤り	config.csvの設定を確認（993, SSL推奨）
no such table: emails	DB未作成	python -m mail_watcher.db.init_db で再生成
Chrome起動時にプロファイルエラー	既存のChromeが動作中	タスクマネージャーで完全終了してから再試行
SKU抽出が0件	メール本文の形式が異なる	extractor.logで確認・改善対象を特定
🧹 DBやログをリフレッシュする場合
DBリセット
python -m mail_watcher.db.init_db

ログリセット

logs/extract.log を開き、すべて削除して上書き保存（空ファイルに）

🏁 プログラム終了方法

常駐中に：

Ctrl + C


を押すと安全に停止します。
（次回起動時は自動的に前回DBを継続使用）

🧩 バージョン

mail_watcher_refactored
構成日：2025-11-03
動作確認：Python 3.11 / Windows 11
