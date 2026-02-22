import os
import sqlite3
from .models import get_db_path

def init_db(config=None):
    """SQLite DBファイルを作成し、テーブルを初期化する"""
    db_path = get_db_path(config)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # --- emails テーブル ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile TEXT,
        provider TEXT,
        message_id TEXT UNIQUE,
        date_utc TEXT,
        from_addr TEXT,
        subject TEXT,
        body_plain TEXT,
        sku TEXT,               -- ★ SKU列あり
        status TEXT,
        content_hash TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    """)

    # --- email_skus テーブル（複数SKU対応用）---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS email_skus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_id INTEGER,
        sku TEXT,
        created_at TEXT,
        FOREIGN KEY (email_id) REFERENCES emails(id)
    );
    """)

    conn.commit()
    conn.close()
    print(f"✅ DB初期化完了: {db_path}")

if __name__ == "__main__":
    config = {"PROFILE": "main"}
    init_db(config)
