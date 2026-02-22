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

orders = Orders(credentials=credentials, marketplace=Marketplaces.JP)

created_after = (datetime.utcnow() - timedelta(days=3)).isoformat()

res = orders.get_orders(
    MarketplaceIds=["A1VC38T7YXB528"],
    OrderStatuses=["Unshipped"],
    CreatedAfter=created_after
)

orders_list = res.payload.get("Orders", [])

print("===== AmazonOrderId 一覧 =====")
for o in orders_list:
    print(o.get("AmazonOrderId"))
