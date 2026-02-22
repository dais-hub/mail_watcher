import os
import sqlite3
import datetime
import subprocess
from ..db.models import get_db_path

# =====================================================
# ログ設定
# =====================================================
# 現在地: src/mail_watcher/services/stock_sync_service.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOG_DIR, "stock_update.log")

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# =====================================================
# 安全なDB接続関数
# =====================================================
def get_safe_connection(db_path):
    conn = sqlite3.connect(db_path, timeout=10)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA busy_timeout=10000;")
    conn.commit()
    return conn

# =====================================================
# メイン同期関数
# =====================================================
def sync_unprocessed_orders(config, dry_run=False):
    db_path = get_db_path(config)
    conn = get_safe_connection(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM emails WHERE status='unprocessed'")
    mails = cur.fetchall()

    if not mails:
        log("⚠️ 未処理メールはありません。")
        conn.close()
        return

    log("=== SKU抽出・在庫更新 開始 ===")
    success_count = 0
    inventory_err_count = 0
    sys_err_count = 0
    retry_count = 0

    for mail in mails:
        mail_id = mail["id"]
        from_addr = mail["from_addr"] or ""
        subject = mail["subject"] or ""
        sku = (mail["sku"] or "").strip()
        if not sku:
            log(f"⚠️ ID {mail_id} | SKU未検出 → スキップ")
            continue

        try:
            # --- メルカリ「購入されました」 ---
            if "mercari" in from_addr.lower() and "購入されました" in subject:
                log(f"🟢 メルカリ購入検知: {sku} → 在庫-1 & payment_pending")
                cmd = [
                    "python",
                    "-m",
                    "mail_watcher.services.decrease_stock_auto",
                    sku,
                ]
                if not dry_run:
                    rc = subprocess.run(cmd).returncode
                else:
                    rc = 0
                    log(f"🧪 [DRY-RUN] メルカリ在庫更新スキップ (購入) | SKU={sku}")

                if rc == 0:
                    cur.execute(
                        "UPDATE emails SET status='payment_pending', updated_at=? WHERE id=?",
                        (datetime.datetime.utcnow().isoformat(), mail_id),
                    )
                    success_count += 1
                    log(f"✅ ID {mail_id} | メルカリ 在庫減算完了 → payment_pending")
                else:
                    cur.execute(
                        "UPDATE emails SET status='inventory_error', updated_at=? WHERE id=?",
                        (datetime.datetime.utcnow().isoformat(), mail_id),
                    )
                    inventory_err_count += 1
                    log(f"⚠️ ID {mail_id} | メルカリ 在庫更新失敗 (rc={rc})")
                conn.commit()
                continue

            # --- メルカリ「発送をお願いします」 ---
            if "mercari" in from_addr.lower() and "発送をお願いします" in subject:
                cur.execute("""
                    SELECT id FROM emails
                    WHERE sku=? AND status='payment_pending'
                    ORDER BY created_at DESC LIMIT 1
                """, (sku,))
                pending = cur.fetchone()

                if pending:
                    log(f"🔵 メルカリ発送検知: {sku} → payment_pending→processed")
                    cur.execute(
                        "UPDATE emails SET status='processed', updated_at=? WHERE id=?",
                        (datetime.datetime.utcnow().isoformat(), pending["id"]),
                    )
                    cur.execute(
                        "UPDATE emails SET status='processed', updated_at=? WHERE id=?",
                        (datetime.datetime.utcnow().isoformat(), mail_id),
                    )
                    conn.commit()
                    continue
                else:
                    log(f"🟣 メルカリ即時決済: {sku} → 在庫-1 & processed")
                    cmd = [
                        "python",
                        "-m",
                        "mail_watcher.services.decrease_stock_auto",
                        sku,
                    ]
                    if not dry_run:
                        rc = subprocess.run(cmd).returncode
                    else:
                        rc = 0
                        log(f"🧪 [DRY-RUN] メルカリ在庫更新スキップ (即時決済) | SKU={sku}")

                    if rc == 0:
                        cur.execute(
                            "UPDATE emails SET status='processed', updated_at=? WHERE id=?",
                            (datetime.datetime.utcnow().isoformat(), mail_id),
                        )
                        success_count += 1
                        log(f"✅ ID {mail_id} | メルカリ 即時決済 processed")
                    else:
                        cur.execute(
                            "UPDATE emails SET status='inventory_error', updated_at=? WHERE id=?",
                            (datetime.datetime.utcnow().isoformat(), mail_id),
                        )
                        inventory_err_count += 1
                        log(f"⚠️ ID {mail_id} | メルカリ 即時決済 在庫更新失敗 (rc={rc})")
                    conn.commit()
                    continue

            # --- Amazon処理 ---
            if "amazon.co.jp" in from_addr.lower():
                log(f"🟦 Amazon受注: SKU={sku}")
                cmd = [
                    "python",
                    "-m",
                    "mail_watcher.services.decrease_stock_auto",
                    sku,
                ]
                if not dry_run:
                    rc = subprocess.run(cmd).returncode
                else:
                    rc = 0
                    log(f"🧪 [DRY-RUN] Amazon在庫更新スキップ | SKU={sku}")

                if rc == 0:
                    cur.execute(
                        "UPDATE emails SET status='processed', updated_at=? WHERE id=?",
                        (datetime.datetime.utcnow().isoformat(), mail_id),
                    )
                    success_count += 1
                    log(f"✅ ID {mail_id} | Amazon 成功")
                else:
                    cur.execute(
                        "UPDATE emails SET status='inventory_error', updated_at=? WHERE id=?",
                        (datetime.datetime.utcnow().isoformat(), mail_id),
                    )
                    inventory_err_count += 1
                    log(f"⚠️ ID {mail_id} | Amazon 在庫更新失敗 (rc={rc})")
                conn.commit()
                continue

        except Exception as e:
            cur.execute(
                "UPDATE emails SET status='system_error', updated_at=? WHERE id=?",
                (datetime.datetime.utcnow().isoformat(), mail_id),
            )
            sys_err_count += 1
            log(f"💥 ID {mail_id} | 例外発生: {e}")

    conn.commit()
    conn.close()
    log("=== SKU抽出・在庫更新 完了 ===")
    log(f"✅ 成功: {success_count} 件")
    log(f"⚠️ 在庫エラー: {inventory_err_count} 件")
    log(f"💥 システム例外: {sys_err_count} 件")
    log(f"🔁 再試行対象: {retry_count} 件")
    log("-" * 60)


# =====================================================
# 後方互換エイリアス
# =====================================================
def run_stock_sync(config, dry_run=False):
    return sync_unprocessed_orders(config, dry_run=dry_run)
