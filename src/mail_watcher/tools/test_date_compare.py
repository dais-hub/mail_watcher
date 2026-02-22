# mail_watcher/tools/test_date_compare.py
import sqlite3
from datetime import datetime
from mail_watcher.db.models import get_db_path
from mail_watcher.config_loader import load_config

def test_date_compare():
    config = load_config()
    db_path = get_db_path(config)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # DB内の最新日時を確認
    cur.execute("SELECT id, date_utc FROM emails ORDER BY id DESC LIMIT 5")
    rows = cur.fetchall()
    print("=== DB中の最新5件 (date_utc) ===")
    for r in rows:
        print(f"ID {r[0]} | {r[1]}")

    # Pythonで生成する cutoff_str
    cutoff_dt = datetime(2025, 11, 5, 10, 28)
    cutoff_str = cutoff_dt.isoformat()
    print(f"\ncutoff_str = {cutoff_str}")

    # 実際に比較されるデータをチェック
    cur.execute("SELECT COUNT(*) FROM emails WHERE date_utc < ?", (cutoff_str,))
    count = cur.fetchone()[0]
    print(f"\n比較結果: date_utc < '{cutoff_str}' → {count} 件ヒット")

    conn.close()

if __name__ == "__main__":
    test_date_compare()
