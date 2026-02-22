# -*- coding: utf-8 -*-
"""
inventory_cache_updater.py (完全安定版)
----------------------------------------
Amazon SP-APIから在庫レポート(GET_MERCHANT_LISTINGS_DATA_LITE)
を取得し、inventory_cache.csvを生成／更新する。
"""

import os
import sys
import time
import csv
import urllib.request
from datetime import datetime
from sp_api.api import Reports
from sp_api.base import Marketplaces, SellingApiException
from mail_watcher.config_loader import load_config

# ------------------------------------------------
# 🧩 パス設定
# ------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
DATA_DIR = os.path.join(BASE_DIR, "data", "cache")
LOG_DIR = os.path.join(BASE_DIR, "logs")
CACHE_FILE = os.path.join(DATA_DIR, "inventory_cache.csv")
LOG_FILE = os.path.join(LOG_DIR, "inventory_cache_update.log")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ------------------------------------------------
# 🧾 ログ出力関数
# ------------------------------------------------
def log_line(level, msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {level:<7} | {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ------------------------------------------------
# 🔐 認証情報ロード
# ------------------------------------------------
def load_credentials():
    try:
        conf = load_config("main")
        creds = {
            "lwa_app_id": conf.get("LWA_CLIENT_ID"),
            "lwa_client_secret": conf.get("LWA_CLIENT_SECRET"),
            "refresh_token": conf.get("LWA_REFRESH_TOKEN"),
            "aws_access_key": conf.get("AWS_ACCESS_KEY"),
            "aws_secret_key": conf.get("AWS_SECRET_KEY"),
            "role_arn": conf.get("ROLE_ARN"),
        }
        seller_id = conf.get("SELLER_ID")
        marketplace_id = conf.get("MARKETPLACE_ID")
        log_line("INFO", "SP-API認証情報を読み込みました。")
        return creds, seller_id, marketplace_id
    except Exception as e:
        log_line("ERROR", f"設定ファイル読み込み失敗: {e}")
        raise

# ------------------------------------------------
# 🕒 キャッシュ更新メイン処理
# ------------------------------------------------
def main(force_update=False):
    start_time = time.time()
    log_line("INFO", "🕒 在庫レポート更新を開始します...")

    # キャッシュが新しい場合はスキップ（force_update=True で強制更新）
    if not force_update and os.path.exists(CACHE_FILE):
        mtime = os.path.getmtime(CACHE_FILE)
        if time.time() - mtime < 86400:
            log_line("INFO", "キャッシュは最新のため更新をスキップしました。")
            return

    try:
        creds, seller_id, marketplace_id = load_credentials()
        reports = Reports(credentials=creds, marketplace=Marketplaces.JP)

        # レポート作成要求
        log_line("INFO", "📋 レポート作成要求: GET_MERCHANT_LISTINGS_DATA_LITE")
        create_resp = reports.create_report(reportType="GET_MERCHANT_LISTINGS_DATA_LITE")
        report_id = create_resp.payload.get("reportId")
        log_line("INFO", f"📄 レポートID: {report_id}")

        # ステータス監視
        for i in range(30):
            status_resp = reports.get_report(report_id)
            processing_status = status_resp.payload.get("processingStatus")
            log_line("INFO", f"⌛ ステータス[{i}]: {processing_status}")
            if processing_status == "DONE":
                break
            time.sleep(6)
        else:
            raise TimeoutError("レポート生成タイムアウト")

        # ドキュメント取得
        doc_id = status_resp.payload.get("reportDocumentId")
        doc = reports.get_report_document(doc_id)
        log_line("INFO", f"📑 ドキュメントID: {doc_id}")

        # レポートデータ取得（sp-apiの仕様変化対応）
        if isinstance(doc.payload, dict) and "url" in doc.payload:
            url = doc.payload["url"]
            with urllib.request.urlopen(url) as response:
                text = response.read().decode("utf-8", errors="ignore").splitlines()
        else:
            text = doc.payload.decode("utf-8", errors="ignore").splitlines()

        # ------------------------------------------------
        # CSV生成（列インデックスベース）
        # ------------------------------------------------
        count = 0
        with open(CACHE_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["sku", "quantity"])
            for line in text:
                parts = line.strip().split("\t")
                if len(parts) >= 2 and parts[0] and parts[1]:
                    sku = parts[0].strip()
                    qty = parts[1].strip()
                    # ヘッダー行スキップ
                    if not sku.lower().startswith(("出品者", "seller", "sku")):
                        writer.writerow([sku, qty])
                        count += 1

        log_line("SUCCESS", f"✅ キャッシュ更新完了！ {count}件")
        log_line("INFO", f"⏱ 所要時間: {time.time() - start_time:.1f} 秒")

    except SellingApiException as e:
        log_line("ERROR", f"SP-APIエラー: {e}")
    except Exception as e:
        log_line("ERROR", f"予期せぬエラー: {e}")

        # 古いキャッシュを残しておく安全処理
        if os.path.exists(CACHE_FILE):
            log_line("WARN", "⚠️ エラー発生のためキャッシュ更新をスキップし、旧キャッシュを保持します。")
        else:
            # キャッシュが存在しない場合のみ、空ファイルを新規作成
            log_line("WARN", "⚠️ キャッシュが存在しないため、空キャッシュを新規作成します。")
            with open(CACHE_FILE, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["sku", "quantity"])

# 別名エクスポート（watchdog_service互換）
def update_cache(force_update=False):
    return main(force_update=force_update)

# ------------------------------------------------
# CLI呼び出し
# ------------------------------------------------
if __name__ == "__main__":
    force = "--force" in sys.argv
    main(force_update=force)
