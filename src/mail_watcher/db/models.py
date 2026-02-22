import os
import sqlite3


def get_db_path(config=None):
    """
    プロジェクト共通の SQLite DB パスを返す。
    旧版では src/data/app.db を指していたが、
    現在は mail_watcher/data/app.db に統一。
    """
    # 現在地: src/mail_watcher/db/models.py
    # → 4階層上がる: db → mail_watcher → src → mail_watcher
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    data_dir = os.path.join(base_dir, "data")

    os.makedirs(data_dir, exist_ok=True)

    db_path = os.path.join(data_dir, "app.db")
    return db_path


def init_db(config=None):
    """
    SQLite DB を初期化し、必要なテーブルを作成する。
    """
    db_path = get_db_path(config)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # --- メールテーブル ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile TEXT,
        provider TEXT,
        message_id TEXT UNIQUE,
        date_utc TEXT,
        from_addr TEXT,
        subject TEXT,
        body_plain TEXT,
        sku TEXT,
        status TEXT,
        content_hash TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # --- SKUテーブル ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS email_skus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_id INTEGER,
        sku TEXT,
        created_at TEXT,
        FOREIGN KEY (email_id) REFERENCES emails (id)
    )
    """)

    conn.commit()
    conn.close()
    print(f"✅ DB初期化完了: {db_path}")
