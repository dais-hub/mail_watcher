import os
import sqlite3
import sys
from textwrap import shorten
from mail_watcher.db.models import get_db_path


def show_unprocessed_summary():
    """未処理メールの簡易リストを表示"""
    from ..db.models import get_db_path
    import sqlite3, os
    from ..config_loader import load_config

    config = load_config()
    db_path = get_db_path(config)

    if not os.path.exists(db_path):
        print(f"⚠️ DBが見つかりません: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_utc, from_addr, subject, sku, status 
        FROM emails 
        WHERE status='unprocessed' 
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("✅ 未処理メールはありません。")
        return

    print(f"=== 未処理メール一覧 ({len(rows)}件) ===")
    for r in rows:
        id_, date_utc, from_addr, subject, sku, status = r
        print(f"📧 ID:{id_} | {date_utc} | {from_addr[:25]} | {subject[:60]} | SKU:{sku or '---'} | {status}")


# ==========================================================
# ✅ DBパス設定（mail_watcher直下の data/app.db を参照）
# ==========================================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
DB_PATH = os.path.join(BASE_DIR, "data", "app.db")

if not os.path.exists(DB_PATH):
    print(f"⚠️ DBが見つかりません: {DB_PATH}")
    sys.exit()

print(f"✅ DB確認済み: {DB_PATH}")

# ==========================================================
# DB接続
# ==========================================================
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ==========================================================
# オプション処理
# ==========================================================
mode = sys.argv[1] if len(sys.argv) > 1 else "latest"

# ==========================================================
# ステータス別件数を表示
# ==========================================================
print("\n=== ステータス別件数 ===")
cur.execute("SELECT status, COUNT(*) FROM emails GROUP BY status")
for status, count in cur.fetchall():
    print(f"{status:<15}: {count}")

# ==========================================================
# 表示モードの選択（skuカラムを追加）
# ==========================================================
if mode.lower() == "all":
    cur.execute("SELECT id, status, from_addr, subject, sku, body_plain FROM emails ORDER BY id DESC")
elif mode.lower() in ["processed", "unprocessed", "sku_missing", "error"]:
    cur.execute("SELECT id, status, from_addr, subject, sku, body_plain FROM emails WHERE status=? ORDER BY id DESC", (mode.lower(),))
else:
    cur.execute("SELECT id, status, from_addr, subject, sku, body_plain FROM emails ORDER BY id DESC LIMIT 10")

rows = cur.fetchall()

# ==========================================================
# 結果を整形して表示（SKU表示付き）
# ==========================================================
print("\n=== emails テーブル ===\n")

if not rows:
    print("(データがありません)")
else:
    for row in rows:
        id_, status, from_addr, subject, sku, body_plain = row
        print(f"📧 ID: {id_} | STATUS: {status} | FROM: {from_addr}")
        print(f"   SUBJECT: {shorten(subject or '', width=100, placeholder='...')}")
        print(f"   SKU: {sku or '(未検出)'}")
        if body_plain:
            preview = shorten(body_plain.replace("\n", " "), width=80, placeholder="...")
            print(f"   BODY: {preview}")
        print("-" * 80)

conn.close()
print("=== 出力完了 ===")
