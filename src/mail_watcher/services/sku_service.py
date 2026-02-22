import os
import sqlite3
import datetime
from ..db.models import get_db_path
from ..parsing.extractor import extract_skus_from_body


# =====================================================
# 安全なDB接続関数（WAL + timeout + busy_timeout）
# =====================================================
def get_safe_connection(db_path):
    """SQLite接続（WALモード＋リトライ設定）"""
    conn = sqlite3.connect(db_path, timeout=10)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA busy_timeout = 10000;")
    conn.commit()
    return conn


# =====================================================
# メイン処理
# =====================================================
def process_emails(config):
    """
    emailsテーブルを走査してSKUを抽出し、email_skusに登録。
    成功・失敗に応じてstatusを更新する。
    """
    db_path = get_db_path(config)
    if not os.path.exists(db_path):
        print(f"⚠️ DBが見つかりません: {db_path}")
        return

    conn = get_safe_connection(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM emails ORDER BY id")
    emails = cur.fetchall()
    if not emails:
        print("⚠️ 処理対象のメールがありません。")
        conn.close()
        return

    print(f"=== SKU抽出処理開始 ({len(emails)}件) ===")

    processed = 0
    missing = 0

    for mail in emails:
        email_id = mail["id"]
        body = mail["body_plain"] or ""
        from_addr = mail["from_addr"] or ""
        marketplace = "amazon" if "amazon" in from_addr else "mercari"

        try:
            # SKU抽出
            skus = extract_skus_from_body(body, marketplace)

            if skus:
                now = datetime.datetime.utcnow().isoformat()
                for sku in skus:
                    cur.execute(
                        """
                        INSERT INTO email_skus (email_id, sku, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (email_id, sku, now),
                    )
                # 成功した場合は「unprocessed」ステータスを維持
                cur.execute(
                    "UPDATE emails SET status = ?, updated_at = ? WHERE id = ?",
                    ("unprocessed", now, email_id),
                )
                processed += 1
                print(f"✅ ID {email_id}: SKU抽出成功 ({len(skus)}件)")
            else:
                now = datetime.datetime.utcnow().isoformat()
                cur.execute(
                    "UPDATE emails SET status = ?, updated_at = ? WHERE id = ?",
                    ("sku_missing", now, email_id),
                )
                missing += 1
                print(f"⚠️ ID {email_id}: SKU未検出")

        except sqlite3.OperationalError as e:
            # database is locked を一時回避
            if "locked" in str(e).lower():
                print(f"⚠️ ID {email_id}: DBロック中 → 再試行待機...")
                conn.commit()
                time.sleep(2)
                continue
            else:
                raise e

    conn.commit()
    conn.close()
    print(f"\n=== SKU抽出処理完了 ===")
    print(f"抽出成功: {processed}件 / 未検出: {missing}件\n")


if __name__ == "__main__":
    config = {"PROFILE": "main"}
    process_emails(config)
