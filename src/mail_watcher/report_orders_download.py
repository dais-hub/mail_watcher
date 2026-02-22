import time
import base64
from datetime import datetime, timedelta

from sp_api.api import Reports
from sp_api.base import Marketplaces, SellingApiException

from config_loader import load_config


# -----------------------------
# SP-API Credentials
# -----------------------------
def load_credentials():
    cfg = load_config()

    return {
        "lwa_app_id": cfg["LWA_CLIENT_ID"],
        "lwa_client_secret": cfg["LWA_CLIENT_SECRET"],
        "refresh_token": cfg["LWA_REFRESH_TOKEN"],
        "aws_access_key": cfg["AWS_ACCESS_KEY"],
        "aws_secret_key": cfg["AWS_SECRET_KEY"],
        "role_arn": cfg["ROLE_ARN"],
    }


# -----------------------------
# レポート作成依頼
# -----------------------------
def request_order_report(days=3):
    creds = load_credentials()

    reports = Reports(
        marketplace=Marketplaces.JP,
        credentials=creds
    )

    data_start = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"

    print(f"レポート生成を依頼します: {data_start}〜現在")

    try:
        res = reports.create_report(
            reportType="GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE",
            dataStartTime=data_start,
        )
        report_id = res.payload.get("reportId")
        print("reportId =", report_id)
        return report_id

    except SellingApiException as e:
        print("レポート作成リクエスト失敗:", e)
        return None


# -----------------------------
# レポート完成待ち
# -----------------------------
def wait_for_report(report_id):
    creds = load_credentials()

    reports = Reports(
        marketplace=Marketplaces.JP,
        credentials=creds
    )

    print("レポート完成待ち…（最大3分程度）")

    for _ in range(60):
        time.sleep(3)
        try:
            status = reports.get_report(report_id)
            processing = status.payload.get("processingStatus")
            print("processingStatus =", processing)

            if processing == "DONE":
                return status.payload.get("reportDocumentId")
        except:
            pass

    print("タイムアウトしました")
    return None


# -----------------------------
# レポートダウンロード
# -----------------------------
def download_report(document_id, filename="orders_report.txt"):
    creds = load_credentials()

    reports = Reports(
        marketplace=Marketplaces.JP,
        credentials=creds
    )

    res = reports.get_report_document(document_id)
    content = res.payload.get("content")

    decoded = base64.b64decode(content).decode("utf-8")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(decoded)

    print(f"\nレポート保存完了: {filename}")


# -----------------------------
# メイン処理
# -----------------------------
def main():
    # ① レポート生成依頼
    report_id = request_order_report(days=7)
    if not report_id:
        return

    # ② 完成待ち
    doc_id = wait_for_report(report_id)
    if not doc_id:
        return

    # ③ ダウンロード
    download_report(doc_id, "orders_report.txt")


if __name__ == "__main__":
    main()
