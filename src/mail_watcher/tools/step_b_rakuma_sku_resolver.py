import argparse
import re
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DEFAULT_PROFILE_DIR = r"C:\Users\daiji\AppData\Local\Programs\Python\Python311\rakuma_db_builder\chrome_rakuma_profile"
DEFAULT_ITEM_ID = "760693767"
SKU_TOKEN_PATTERN = r"[A-Z][A-Z0-9]{1,4}-\d{6}-\d{6,8}-\d{1,2}"
SKU_TOKEN_RE = re.compile(rf"^{SKU_TOKEN_PATTERN}$")


def build_shipping_url(item_id: str) -> str:
    return f"https://web.fril.jp/v2/sale/shipping?is_web=1&item_id={item_id}"


def extract_sku_from_text(text: str) -> str:
    # 「完全一致」要件に合わせ、トークン単位で fullmatch 判定する
    # 先頭: 英大文字
    # プレフィックス全長: 2〜5（英大文字+数字）
    # 後続: -6桁 -6〜8桁 -1〜2桁
    candidates = re.split(r"[^A-Z0-9-]+", (text or "").upper())
    for token in candidates:
        if SKU_TOKEN_RE.fullmatch(token):
            return token
    return ""


def open_driver(profile_dir: str, headless: bool = False):
    options = Options()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)


def resolve_sku(order_id: str, item_id: str, profile_dir: str, click_banner: bool = False, headless: bool = False) -> str:
    shipping_url = build_shipping_url(item_id)
    print(f"[INFO] order_id={order_id}")
    print(f"[INFO] item_id={item_id}")
    print(f"[INFO] shipping_url={shipping_url}")
    print(f"[INFO] profile_dir={profile_dir}")

    driver = open_driver(profile_dir=profile_dir, headless=headless)
    wait = WebDriverWait(driver, 25)

    try:
        driver.get(shipping_url)

        banner = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.bridge-item.row.item_detail_banner"))
        )

        item_url = banner.get_attribute("data-url") or ""
        if click_banner:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.bridge-item.row.item_detail_banner")))
            banner.click()
            time.sleep(2)
            if item_url and item_url not in driver.current_url:
                driver.get(item_url)
        else:
            if not item_url:
                raise RuntimeError("shippingページから data-url を取得できませんでした")
            driver.get(item_url)

        desc = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.item__description__line-limited"))
        )
        desc_text = desc.text

        sku = extract_sku_from_text(desc_text)
        if not sku:
            raise RuntimeError("商品説明欄からSKUを抽出できませんでした")

        print(f"[SUCCESS] extracted_sku={sku}")
        return sku

    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(
        description="Step B: Rakuma shippingページ→商品ページ説明欄からSKUを抽出"
    )
    parser.add_argument("--order-id", default="824971570", help="評価用オーダーID文字列")
    parser.add_argument("--item-id", default=DEFAULT_ITEM_ID, help="shipping URL生成用 item_id")
    parser.add_argument("--profile-dir", default=DEFAULT_PROFILE_DIR, help="Chromeユーザープロファイル")
    parser.add_argument("--click-banner", action="store_true", help="data-url遷移の代わりにバナーをクリック")
    parser.add_argument("--headless", action="store_true", help="ヘッドレス実行")
    args = parser.parse_args()

    profile_path = Path(args.profile_dir)
    if not profile_path.exists():
        print(f"[WARN] profile_dir が存在しません: {profile_path}")

    try:
        resolve_sku(
            order_id=args.order_id,
            item_id=args.item_id,
            profile_dir=str(profile_path),
            click_banner=args.click_banner,
            headless=args.headless,
        )
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
