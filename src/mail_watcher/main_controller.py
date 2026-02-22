# =====================================================
# mail_watcher main_controller.py (安定修正版)
# =====================================================

import os
import time
from datetime import datetime

import sqlite3
from mail_watcher.db.models import get_db_path
from mail_watcher.db.init_db import init_db
from mail_watcher.services.fetch_service_imap import main as fetch_mails
from mail_watcher.services.stock_sync_service import run_stock_sync
from mail_watcher.config_loader import load_config

import email.utils  # RFC2822パースに便利
from datetime import datetime, timezone, timedelta

# =====================================================
# 定数・パス設定
# =====================================================
# 現在地: src/mail_watcher/main_controller.py
# → 3階層上がる: mail_watcher → src → mail_watcher
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# =====================================================
# メルカリログインプロファイル作成
# =====================================================
def create_mercari_profile(force=False):
    from mail_watcher.services.mercari_update_stock_fullflow_v10_interactfix import update_stock_minus1
    profile_dir = os.path.expanduser("~/AppData/Local/Google/Chrome/User Data/mailwatcher_mercari")

    if os.path.exists(profile_dir) and not force:
        print(f"✅ 既存のログインプロファイルを検出: {profile_dir}")
        print("スキップします。再作成したい場合は、force=True で呼び出してください。")
        return

    print("⚙️ Chromeが起動します。メルカリShopsのログインページが開いたら、手動でログインしてください。")
    print("ログイン後、Enterキーを押すまでウィンドウは閉じません。")
    try:
        update_stock_minus1("AB-123456-789012-0", hold_browser=True)
        input("✅ ログインが完了したら Enter を押してください...")
    except Exception as e:
        print(f"❌ ログインプロファイル作成中にエラー: {e}")
    print("✅ ログインプロファイル作成が完了しました。この作業は一度きりでOKです。")


# =====================================================
# 指定時刻以前のメールを processed にマーク
# =====================================================
def mark_emails_as_processed_before(config, cutoff_dt):
    import sqlite3
    from mail_watcher.db.models import get_db_path

    db_path = get_db_path(config)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id, date_utc FROM emails WHERE status!='processed'")
    rows = cur.fetchall()

    # 🕐 入力（JST）→ UTC に変換
    jst = timezone(timedelta(hours=9))
    cutoff_utc = cutoff_dt.replace(tzinfo=jst).astimezone(timezone.utc)

    updated = 0
    for row_id, date_utc in rows:
        try:
            msg_dt = email.utils.parsedate_to_datetime(date_utc)
            msg_dt_utc = msg_dt.astimezone(timezone.utc)

            if msg_dt_utc < cutoff_utc:
                cur.execute("UPDATE emails SET status='processed' WHERE id=?", (row_id,))
                updated += 1
        except Exception as e:
            print(f"⚠️ ID {row_id} の日付変換失敗: {e}")

    conn.commit()
    conn.close()
    print(f"✅ {updated} 件のメールを {cutoff_dt.isoformat()}（JST基準）より前として processed に変更しました。")


# =====================================================
# メイン制御ループ
# =====================================================
def main():
    print("=== mail_watcher メインコントローラ ===")

    try:
        config = load_config()
    except Exception as e:
        print(f"❌ 設定ファイルの読み込みに失敗しました: {e}")
        return

    while True:
        print("\n=== メインメニュー ===")
        print("1. 過去2週間のメールをDB化")
        print("2. メルカリログインプロファイル作成")
        print("3. 同期開始時刻を設定")
        print("4. DBの内容を確認（未処理メールの一覧）")
        print("5. 常駐監視モード（立ち上げで未処理分を一括処理、その後3分周期でチェック）")
        print("6. メルカリ支払い待ちオーダーの確認・更新")
        print("7. 終了")

        choice = input("番号を入力してください：").strip()

        # -------------------------------------------------
        if choice == "1":
            print("\n=== ① DB初期化とメール取得 ===")
            init_db()
            fetch_mails()
            print("✅ メールDB化完了。")

            # --- 追加部分：自動で SKU 抽出を実行 ---
            print("\n📦 メールDB化が完了しました。続いてSKU抽出を行います…")
            try:
                os.system("python -m mail_watcher.parsing.extractor")
                print("✅ SKU抽出処理が完了しました。\n")
            except Exception as e:
                print(f"⚠️ SKU抽出処理中にエラー: {e}")

        # -------------------------------------------------
        elif choice == "2":
            print("\n=== ② メルカリログインプロファイル作成 ===")
            force = input("既存プロファイルを上書きしますか？(y/N): ").lower() == "y"
            create_mercari_profile(force)

        # -------------------------------------------------
        elif choice == "3":
            print("\n=== ③ 同期開始時刻を設定 ===")
            try:
                y = int(input("年："))
                m = int(input("月："))
                d = int(input("日："))
                hh = int(input("時(0-24)："))
                mm = int(input("分(0-59)："))
                cutoff_dt = datetime(y, m, d, hh, mm)
                mark_emails_as_processed_before(config, cutoff_dt)
            except Exception as e:
                print(f"❌ 入力エラー: {e}")

        # -------------------------------------------------
        elif choice == "4":
            from mail_watcher.db.models import get_db_path
            import sqlite3
            db_path = get_db_path(config)

            print("\n=== 未処理メール一覧 (status='unprocessed') ===")
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("SELECT id, from_addr, subject, sku, status FROM emails WHERE status='unprocessed' ORDER BY id DESC")
                rows = cur.fetchall()
                conn.close()

                if not rows:
                    print("📭 未処理メールはありません。\n")
                else:
                    for r in rows:
                        mail_id, from_addr, subject, sku, status = r
                        print(f"🆔 {mail_id:<3} | {status:<12} | {from_addr:<35} | SKU: {sku or '(未検出)'}")
                        print(f"     SUBJECT: {subject[:90]}{'...' if len(subject)>90 else ''}")
                        print("-" * 80)

                print("=== 出力完了 ===\n")
            except Exception as e:
                print(f"⚠️ DB読み込みエラー: {e}\n")

#        # -------------------------------------------------
#        elif choice == "5":
#            try:
#                from mail_watcher.services.stock_sync_service import sync_unprocessed_orders
#                print("\n=== 一斉在庫同期処理 ===")
#                print("status='unprocessed' のメールに含まれるSKUを対象に、Amazonとメルカリの在庫を1減算します。")
#                # dry_runを常にFalse（実際に実行）
#                dry_run = False
#
#                print("\n在庫同期を開始します...")
#                sync_unprocessed_orders(config, dry_run=dry_run)
#                print("=== 一斉同期処理が完了しました ===\n")
#            except Exception as e:
#                print(f"⚠️ 同期処理中にエラー: {e}\n")
#
        # -------------------------------------------------
        elif choice == "5":
            from mail_watcher.services import watchdog_service
            watchdog_service.run_watchdog()

        # -------------------------------------------------
        elif choice == "6":
            print("=== 支払い待ちオーダーの確認・更新 ===")
            try:
                db_path = get_db_path()
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()

                # payment_pending 一覧を取得
                cur.execute("""
                    SELECT id, subject, sku, from_addr, created_at
                    FROM emails
                    WHERE status = 'payment_pending'
                    ORDER BY created_at ASC
                """)
                rows = cur.fetchall()

                if not rows:
                    print("✅ 現在、支払い待ちのオーダーはありません。")
                    conn.close()
                    return

                print("\n📋 現在、支払い待ちのオーダー一覧：\n")
                for row in rows:
                    id_, subject, sku, from_addr, created_at = row
                    created_at_str = created_at.split("T")[0] if created_at else "N/A"
                    print(f"・日付: {created_at_str} | SKU: {sku} | 件名: {subject} | From: {from_addr}")

                print("\nこれらのオーダーをすべて 'processed（終了）' に変更しますか？")
                confirm = input("Yで実行 / Nでキャンセル: ").strip().lower()

                if confirm == "y":
                    cur.execute(
                        "UPDATE emails SET status='processed', updated_at=? WHERE status='payment_pending'",
                        (datetime.utcnow().isoformat(),)
                    )
                    affected = cur.rowcount
                    conn.commit()
                    print(f"✅ {affected} 件のレコードを更新しました。")
                else:
                    print("🚫 更新をキャンセルしました。")

                conn.close()

            except Exception as e:
                print(f"❌ 処理中にエラーが発生しました: {e}")

        # -------------------------------------------------
        elif choice == "7":
            print("プログラムを終了します。")
            break

        else:
            print("⚠️ 無効な選択です。1〜7を入力してください。")


if __name__ == "__main__":
    main()
