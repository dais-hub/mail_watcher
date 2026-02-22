import os
import sqlite3

def get_db_path():
    """
    プロジェクト全体で共通の DB パスを返す。
    mail_watcher/data/app.db を常に参照する。
    """
    # このファイルの位置: src/mail_watcher/utils/db_utils.py
    # → 3階層上がる: utils → mail_watcher → src
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    db_path = os.path.join(base_dir, "data", "app.db")
    return db_path


def get_db_connection():
    """
    共通の SQLite 接続を取得。
    - WALモードを有効化（並行アクセス安全）
    - busy_timeoutを設定（ロック競合時のリトライ耐性）
    - ディレクトリが存在しない場合は自動作成
    """
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def safe_execute(cur, query, params=None):
    """
    シンプルな安全実行ラッパー。
    例外発生時はログを返し、処理を止めない。
    """
    try:
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        return True
    except sqlite3.OperationalError as e:
        print(f"⚠️ SQL実行エラー: {e}")
        return False
