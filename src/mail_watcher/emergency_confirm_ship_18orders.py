from sp_api.api import Orders
from sp_api.base import Marketplaces
from config_loader import load_config
from datetime import datetime, timedelta

cfg = load_config()

credentials = {
    "lwa_app_id": cfg["LWA_CLIENT_ID"],
    "lwa_client_secret": cfg["LWA_CLIENT_SECRET"],
    "refresh_token": cfg["LWA_REFRESH_TOKEN"],
    "aws_access_key": cfg["AWS_ACCESS_KEY"],
    "aws_secret_key": cfg["AWS_SECRET_KEY"],
    "role_arn": cfg["ROLE_ARN"],
}

def get_unshipped_orders():
    api = Orders(credentials=credentials, marketplace=Marketplaces.JP)
    created_after = (datetime.utcnow() - timedelta(days=7)).isoformat()

    res = api.get_orders(
        MarketplaceIds=["A1VC38T7YXB528"],
        OrderStatuses=["Unshipped"],
        CreatedAfter=created_after
    )

    return [o["AmazonOrderId"] for o in res.payload.get("Orders", [])]


def send_shipment(order_id):
    api = Orders(credentials=credentials, marketplace=Marketplaces.JP)

    payload = {
        "packageReferenceId": "pkg-1",
        "carrierCode": "OTHER",
        "trackingNumber": ""
    }

    try:
        # ここが決定版！
        result = api.confirm_shipment(
            order_id,
            shipmentRequestDetails=payload
        )
        print(f"[OK] 発送通知: {order_id}")
        return result

    except Exception as e:
        print(f"[ERR] {order_id}: {e}")
        return None


def main():
    ids = get_unshipped_orders()

    print("=== 未発送注文 ===")
    for oid in ids:
        print(oid)
    print(f"\n合計 {len(ids)} 件\n")

    if input("全件発送通知しますか？ [y/N]: ").lower() != "y":
        print("キャンセル")
        return

    for oid in ids:
        send_shipment(oid)

    print("\n=== 発送通知 完了 ===")


if __name__ == "__main__":
    main()
