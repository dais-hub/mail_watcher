# -*- coding: utf-8 -*-
"""
watchdog_service.py (安定統合版)
----------------------------------------
メールDBを常駐監視し、未処理メールに応じて在庫を同期します。
- メルカリ販売 → Amazon在庫を減算
- Amazon販売 → メルカリ在庫を減算
- DBロック耐性 (WAL + busy_timeout)
- 24時間ごとの在庫キャッシュ更新
"""

import os
import sys
import time
import datetime
import sqlite3
import subprocess

from mail_watcher.config_loader import load_config
from mail_watcher.utils.db_utils import get_db_connection, get_db_path
from mail_watcher.services.inventory_cache_updater import update_cache
from mail_watcher.services.fetch_service_imap import main as fetch_mails
from mail_watcher.parsing.extractor import main as extract_skus

# 🌟 python-amazon-sp-api の寄付メッセージを非表示
os.environ["ENV_DISABLE_DONATION_MSG"] = "1"

# ------------------------------------------------------------
# 🧩 パス設定
# ------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../../.."))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "watchdog.log")

# ------------------------------------------------------------
# 🧾 ログ関数
# ------------------------------------------------------------
def log_line(level, msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {level:<7} | {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ------------------------------------------------------------
# 🧩 補助関数
# ------------------------------------------------------------
def _looks_like_mercari(from_addr):
    return "mercari" in from_addr.lower()

def _looks_like_amazon(from_addr):
    return "amazon.co.jp" in from_addr.lower()

# ------------------------------------------------------------
# 📦 メイン処理
# ------------------------------------------------------------
def main():
    log_line("INFO", "🔍 未処理メールの監視開始...")

    conn = get_db_connection()
    cur = conn.cursor()

    # ------------------------------------------------------------
    # 🗓 起動時に在庫キャッシュ確認（メールがなくても必ず実行）
    # ------------------------------------------------------------
    cache_file = os.path.join(CACHE_DIR, "inventory_cache.csv")
    need_cache_update = (
        not os.path.exists(cache_file)
        or (time.time() - os.path.getmtime(cache_file)) > 86400
    )

    # ✅ メールDBを最新化（過去2週間分など）
    try:
        log_line("INFO", "📨 新着メールを取得しています...")
        fetch_mails()
        log_line("INFO", "🔎 メール本文からSKUを抽出しています...")
        extract_skus()   # ←これを追加！
    except Exception as e:
        log_line("ERROR", f"メール取得中にエラー: {e}")

    if need_cache_update:
        log_line("INFO", "🗓 在庫キャッシュを更新中...")
        try:
            update_cache()
        except Exception as e:
            log_line("ERROR", f"在庫キャッシュ更新失敗: {e}")

    # ------------------------------------------------------------
    # 📬 未処理メールの抽出
    # ------------------------------------------------------------
    cur.execute("""
        SELECT id, from_addr, subject, sku, status
        FROM emails
        WHERE status = 'unprocessed'
        ORDER BY id ASC
    """)
    rows = cur.fetchall()

    if not rows:
        log_line("INFO", "未処理メールなし。")
        conn.close()
        return

    # ------------------------------------------------------------
    # 📦 各メール処理
    # ------------------------------------------------------------
    for row in rows:
        id_, from_addr, subject, sku, status = row

        if not sku:
            log_line("WARN", f"ID={id_}: SKU未検出、スキップ。")
            continue

        try:
            # --------------------------------------------------
            # メルカリ販売 → Amazon在庫を減算
            # --------------------------------------------------
            if _looks_like_mercari(from_addr):
                if "購入されました" in subject:
                    log_line("INFO", f"🟩 メルカリ購入通知: SKU={sku}")
                    log_line("INFO", f"    件名: {subject}")   # ← 追加！
                    subprocess.run(
                        ["python", "-m", "mail_watcher.services.decrease_stock_auto", sku]
                    )
                    new_status = "payment_pending"
                else:
                    # 「発送をお願いします」など
                    log_line("INFO", f"🟩 メルカリ発送通知: SKU={sku}")
                    log_line("INFO", f"    件名: {subject}")   # ← 追加！
                    if status == "payment_pending":
                        new_status = "processed"
                    else:
                        subprocess.run(
                            ["python", "-m", "mail_watcher.services.decrease_stock_auto", sku]
                        )
                        new_status = "processed"

            # --------------------------------------------------
            # Amazon販売 → メルカリ在庫を減算
            # --------------------------------------------------
            elif _looks_like_amazon(from_addr):
                log_line("INFO", f"🟦 Amazon受注: SKU={sku}")
                log_line("INFO", f"    件名: {subject}")   # ← 追加！
                subprocess.run(
                    ["python", "-m", "mail_watcher.services.mercari_update_stock_fullflow_v10_interactfix", sku]
                )
                new_status = "processed"

            # --------------------------------------------------
            # その他
            # --------------------------------------------------
            else:
                log_line("WARN", f"ID={id_}: 未対応メール種別 from={from_addr}")
                new_status = "ignored"

            # --------------------------------------------------
            # ステータス更新
            # --------------------------------------------------
            # ステータス更新（同一メール内の全SKUをまとめて更新）
            cur.execute("""
                UPDATE emails
                SET status=?, updated_at=?
                WHERE message_id IN (
                    SELECT message_id FROM emails WHERE id=?
                )
            """, (
                new_status,
                datetime.datetime.utcnow().isoformat(),
                id_,
            ))
            conn.commit()
            log_line("DEBUG", f"message_id一致メール群を {new_status} に更新完了。ID={id_}")

        except Exception as e:
            log_line("ERROR", f"ID={id_}: 在庫処理中にエラー発生 → {e}")
            conn.rollback()

    conn.close()
    log_line("INFO", "=== 監視サイクル完了 ===")


# ------------------------------------------------------------
# 🔁 常駐監視モード
# ------------------------------------------------------------
def run_watchdog():
    CACHE_REFRESH_INTERVAL = 10800  # 3時間ごとにキャッシュ更新
    last_cache_update = 0

    while True:
        try:
            main()  # メール監視・在庫処理のメイン部分を実行

            # === 🕒 ここから追加部分 ===
            now = time.time()
            if now - last_cache_update > CACHE_REFRESH_INTERVAL:
                log_line("INFO", "🗓 定期キャッシュ更新（1時間経過）...")
                try:
                    subprocess.run(
                        ["python", "-m", "mail_watcher.services.inventory_cache_updater", "--force"],
                        check=True,
                    )
                    last_cache_update = now
                    log_line("INFO", "✅ 定期キャッシュ更新完了。")
                except Exception as e:
                    log_line("ERROR", f"定期キャッシュ更新中にエラー発生: {e}")
            # === 🕒 追加ここまで ===

            time.sleep(180)  # 3分周期

        except KeyboardInterrupt:
            log_line("INFO", "手動停止されました。")
            break
        except Exception as e:
            log_line("ERROR", f"監視中にエラー発生: {e}")
            time.sleep(30)


# ------------------------------------------------------------
if __name__ == "__main__":
    run_watchdog()
