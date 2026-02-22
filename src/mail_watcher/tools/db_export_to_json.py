import os
import json
import sqlite3
from mail_watcher.db.models import get_db_path


def export_to_json(output_path="emails_export.json", table="emails"):
    """
    SQLite DB から指定テーブルを JSON ファイルにエクスポートします。
    HTML本文や改行・カンマを含むデータでも安全に扱えます。
    """

    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"⚠️ DBが見つかりません: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    data = [dict(zip(columns, row)) for row in rows]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    conn.close()
    print(f"✅ {len(rows)} 件を {output_path} にエクスポートしました。")


if __name__ == "__main__":
    export_to_json()
