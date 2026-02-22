# src/mail_watcher/tools/add_sku_column.py
import sqlite3
import os
from mail_watcher.db.models import get_db_path
from mail_watcher.config_loader import load_config

config = load_config()
db_path = get_db_path(config)

conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("ALTER TABLE emails ADD COLUMN sku TEXT")
    print("✅ emails テーブルに sku 列を追加しました。")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("⚠️ sku 列はすでに存在します。")
    else:
        raise

conn.commit()
conn.close()
