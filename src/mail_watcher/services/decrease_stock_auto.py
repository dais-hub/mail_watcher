# -*- coding: utf-8 -*-
"""
decrease_stock_auto.py  (v2.2)
----------------------------------------
MFN（自社出荷）在庫管理用の安定版。
SP-APIで在庫を減算し、ローカルキャッシュを同期更新します。
main_controller / stock_sync_service からの subprocess 呼び出しにも対応。
"""

import os, sys
import io
import time
import datetime
import csv
from filelock import FileLock
from sp_api.api import ListingsItems
from sp_api.base import Marketplaces, SellingApiException
from mail_watcher.config_loader import load_config

# --------------------------------------------------
# 🧩 パス解決・環境設定
# --------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../../.."))

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# 🌟 python-amazon-sp-api の寄付メッセージを非表示
os.environ["ENV_DISABLE_DONATION_MSG"] = "1"

# UTF-8 出力設定（PowerShell対応）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
    sys.stderr.reconfigure(encoding="utf-8", errors="ignore")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="ignore")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="ignore")

# --------------------------------------------------
# 🧩 共通ディレクトリ設定
# --------------------------------------------------
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
LOG_DIR = os.path.join(BASE_DIR, "logs")
CONFIG_DIR = os.path.join(BASE_DIR, "config")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# --------------------------------------------------
# 🧩 キャッシュ・ログパス
# --------------------------------------------------
CACHE_FILE = os.path.join(CACHE_DIR, "inventory_cache.csv")
LOG_FILE = os.path.join(LOG_DIR, "amazon_stock_update.log")

# --------------------------------------------------
# 📜 ログ出力
# --------------------------------------------------
def log_line(level: str, msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {level:<7} | {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# --------------------------------------------------
# 🔐 認証情報読み込み
# --------------------------------------------------
def init_credentials():
    global creds, SELLER_ID, MARKETPLACE_ID
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
        SELLER_ID = conf.get("SELLER_ID")
        MARKETPLACE_ID = conf.get("MARKETPLACE_ID")
        log_line("INFO", "SP-API認証情報ロード完了")
    except Exception as e:
        log_line("ERROR", f"設定読込失敗: {e}")
        sys.exit(1)

# --------------------------------------------------
# 📦 在庫キャッシュ取得
# --------------------------------------------------
def get_current_stock(sku: str):
    try:
        if not os.path.exists(CACHE_FILE):
            log_line("WARN", f"{sku}: キャッシュが存在しません。仮在庫 1 として処理。")
            return 1

        with open(CACHE_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("sku") == sku:
                    qty = int(row.get("quantity", "0"))
                    log_line("INFO", f"{sku}: キャッシュ在庫 {qty}")
                    return qty

        log_line("WARN", f"{sku}: cacheにSKUが見つかりません。仮在庫 1 として処理。")
        return 1

    except Exception as e:
        log_line("ERROR", f"{sku}: 在庫キャッシュ読取エラー {e}")
        return 1

# --------------------------------------------------
# 💾 キャッシュ更新（ファイルロック付き）
# --------------------------------------------------
def update_local_cache(sku: str, new_qty: int):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    lock_path = CACHE_FILE + ".lock"
    tmp_file = CACHE_FILE + ".tmp"

    with FileLock(lock_path, timeout=10):
        if not os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["sku", "quantity"])

        found = False
        with open(CACHE_FILE, "r", encoding="utf-8-sig") as f_in, open(tmp_file, "w", newline="", encoding="utf-8") as f_out:
            reader = csv.DictReader(f_in)
            fieldnames = reader.fieldnames or ["sku", "quantity"]
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                if row.get("sku") == sku:
                    row["quantity"] = str(new_qty)
                    found = True
                writer.writerow(row)

            if not found:
                writer.writerow({"sku": sku, "quantity": str(new_qty)})

        os.replace(tmp_file, CACHE_FILE)
        log_line("INFO", f"{sku}: キャッシュ在庫を {new_qty} に更新しました。")

# --------------------------------------------------
# 🧮 在庫1減算処理
# --------------------------------------------------
def decrease_stock(sku: str):
    qty = get_current_stock(sku)
    if qty <= 0:
        log_line("WARN", f"{sku}: 在庫0のため減算スキップ")
        return 2

    new_qty = max(0, qty - 1)
    api = ListingsItems(credentials=creds, marketplace=Marketplaces.JP)

    try:
        api.patch_listings_item(
            sellerId=SELLER_ID,
            sku=sku,
            body={
                "productType": "PRODUCT",
                "patches": [
                    {
                        "op": "replace",
                        "path": "/attributes/fulfillment_availability",
                        "value": [
                            {
                                "fulfillment_channel_code": "DEFAULT",
                                "quantity": new_qty
                            }
                        ],
                    }
                ],
            },
        )
        log_line("SUCCESS", f"{sku}: 在庫 {qty} → {new_qty} に更新完了")
        update_local_cache(sku, new_qty)
        return 0

    except SellingApiException as e:
        log_line("ERROR", f"{sku}: 在庫更新SPAPIエラー {e}")
        return 3
    except Exception as e:
        log_line("ERROR", f"{sku}: 在庫更新一般エラー {e}")
        return 4

# --------------------------------------------------
# 🚀 CLI 実行
# --------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("⚠ SKUを指定してください。例: python decrease_stock_auto.py AB-123456-789012-0")
        sys.exit(1)

    sku = sys.argv[1].strip()
    if sku.startswith("TEST-"):
        print(f"⚠ テストSKU {sku} はスキップされます。")
        sys.exit(0)

    init_credentials()
    rc = decrease_stock(sku)
    sys.exit(rc)

if __name__ == "__main__":
    main()
