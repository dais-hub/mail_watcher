from sp_api.api import Shipping
from config_loader import load_config

cfg = load_config()

credentials = {
    "lwa_app_id": cfg["LWA_CLIENT_ID"],
    "lwa_client_secret": cfg["LWA_CLIENT_SECRET"],
    "refresh_token": cfg["LWA_REFRESH_TOKEN"],
    "aws_access_key": cfg["AWS_ACCESS_KEY"],
    "aws_secret_key": cfg["AWS_SECRET_KEY"],
    "role_arn": cfg["ROLE_ARN"],
}

sh = Shipping(credentials=credentials)

print(dir(sh))
