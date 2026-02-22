import sys
sys.stdout.reconfigure(encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} | ACTION | {msg}")

def update_stock_minus1(sku_code: str, hold_browser=False):
    options = Options()
    options.add_argument(r"--user-data-dir=C:\Users\daiji\AppData\Local\Google\Chrome\SeleniumProfile")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)

    try:
        log("🛍️ メルカリ商品一覧ページを開きました")
        driver.get("https://mercari-shops.com/seller/shops/DMZw4jWnetZo9QSQBsoACB/products")

        # SKU検索欄を待機
        search_box = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='search-input']"))
        )

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", search_box)
        driver.execute_script("arguments[0].click();", search_box)
        driver.execute_script("arguments[0].focus();", search_box)
        time.sleep(0.5)

        search_box.clear()
        search_box.send_keys(sku_code)
        time.sleep(0.5)
        search_box.send_keys("\n")
        log(f"🔍 SKU '{sku_code}' を検索しました")
        time.sleep(3)

        # 検索結果の最初の商品をクリック
        first_product = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "p[data-testid='product-name']"))
        )
        first_product.click()
        log("✅ 商品ページを開きました")

        # 🪟 新しいタブに切り替え
        time.sleep(2)
        tabs = driver.window_handles
        if len(tabs) > 1:
            driver.switch_to.window(tabs[-1])
            log("🪟 新しいタブに切り替えました")
        else:
            log("⚠️ 新しいタブが検出されませんでした。仕様変更を再確認してください。")

        time.sleep(3)

        # 在庫入力欄を待機
        qty_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='type-and-inventory-number']"))
        )

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", qty_input)
        time.sleep(0.5)
        driver.execute_script("arguments[0].focus();", qty_input)

        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='type-and-inventory-number']"))
        )

        current_qty = int(qty_input.get_attribute("value"))
        new_qty = max(0, current_qty - 1)
        log(f"📦 在庫数入力: {current_qty} → {new_qty}")

        qty_input.clear()
        qty_input.send_keys(str(new_qty))
        time.sleep(1)

        # 公開設定に進む
        publish_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//p[contains(text(),'公開設定に進む')]"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", publish_button)
        publish_button.click()
        log("➡️ 『公開設定に進む』クリック")

        # 更新する
        update_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='publish-button']"))
        )
        update_button.click()
        log("💾 『更新する』ボタンをクリックしました")

        WebDriverWait(driver, 20).until(
            EC.url_contains("/products")
        )
        log("✅ 在庫変更完了。商品一覧ページに戻りました。")

        # ↩️ 商品ページタブを閉じて一覧に戻る
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            log("↩️ 商品ページを閉じ、一覧タブに戻りました。")

    except Exception as e:
        log(f"⚠️ エラー発生: {e}")

    finally:
        if hold_browser:
            log("⏸️ hold_browser=True のため、ブラウザを保持します。")
            input("Enterキーを押すとブラウザを閉じます。")
        driver.quit()


# ==============================
# 実行部分
# ==============================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ SKUコードを指定してください。例: python mercari_update_stock_fullflow_v10_interactfix.py AB-123456-789012-0")
        sys.exit(1)
    sku_code = sys.argv[1]
    hold_browser = "--hold" in sys.argv
    update_stock_minus1(sku_code, hold_browser)
