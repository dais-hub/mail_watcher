# src/mail_watcher/services/fetch_service.py
import datetime
import hashlib
import sqlite3
from ..db.models import get_db_path

def import_emails(config):
    """
    現状はダミー挿入のみ（メール取得は後で実装）
    """
    db_path = get_db_path(config)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    now = datetime.datetime.utcnow().isoformat()
    sample_mails = [
        {
            "message_id": f"dummy-{i}",
            "date_utc": now,
            "from_addr": config.get("FROM_FILTER_AMAZON", ""),
            "subject": f"サンプル受注メール {i}",
            "body_plain": f"これはテスト本文です。SKU: TESTSKU-{i}",
            "status": "unprocessed",
        }
        for i in range(3)
    ]

    for mail in sample_mails:
        h = hashlib.sha1(mail["body_plain"].encode("utf-8")).hexdigest()
        c.execute("""
            INSERT INTO emails (profile, provider, message_id, date_utc, from_addr, subject, body_plain, status, content_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            config.get("PROFILE", "main"),
            config.get("MAIL_PROVIDER", "imap"),
            mail["message_id"],
            mail["date_utc"],
            mail["from_addr"],
            mail["subject"],
            mail["body_plain"],
            mail["status"],
            h,
            now,
            now
        ))

    conn.commit()
    conn.close()
    print(f"{len(sample_mails)} 件のメールをDBに登録しました。")

# -----------------------------------------------
# テスト実行ブロック
# -----------------------------------------------
if __name__ == "__main__":
    # テスト用の簡易設定
    config = {
        "PROFILE": "main",
        "MAIL_PROVIDER": "imap",
        "FROM_FILTER_AMAZON": "seller-notification@amazon.co.jp",
    }
    print("=== ダミーメール登録テスト開始 ===")
    import_emails(config)
    print("=== ダミーメール登録テスト完了 ===")
