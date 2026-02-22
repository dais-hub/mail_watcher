import os
import json
import sqlite3
from mail_watcher.db.models import get_db_path


def import_from_json(json_path="emails_export.json", table="emails", replace=True):
    """
    JSON ファイルを SQLite DB の指定テーブルにインポートします。
    既存データを上書きするかは replace=True/False で選択。
    """

    db_path = get_db_path()
    if not os.path.exists(json_path):
        print(f"⚠️ JSONファイルが見つかりません: {json_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        print("⚠️ JSON内にデータがありません。")
        conn.close()
        return

    if replace:
        print(f"⚠️ 既存の {table} テーブルを全削除して上書きします。")
        cur.execute(f"DELETE FROM {table}")

    columns = data[0].keys()
    placeholders = ",".join(["?"] * len(columns))
    sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"

    cur.executemany(sql, [tuple(item[col] for col in columns) for item in data])
    conn.commit()
    conn.close()

    print(f"✅ {len(data)} 件を {table} にインポートしました。")


if __name__ == "__main__":
    import_from_json()
