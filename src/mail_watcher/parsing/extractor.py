import os, re, sqlite3, datetime
from ..db.models import get_db_path

NONSPACE_TOKEN = r"[^\s\u3000<>]+"

ANCHOR_PATTERNS = [
    rf"商品管理コード\s*[:：]\s*({NONSPACE_TOKEN})",
    rf"商品管理番号\s*[:：]\s*({NONSPACE_TOKEN})",
    rf"SKU\s*[:：]\s*({NONSPACE_TOKEN})",
    rf"注文確定\s*[:：]\s*(?!\d+点の商品が)([^\s\u3000<>]+)",
]

RAKUMA_ORDER_ID_PATTERN = r"オーダーID\s*[:：]\s*(\d{6,9})"

def strip_html_to_text(s: str) -> str:
    if not s:
        return ""
    t = re.sub(r"<\s*br\s*/?\s*>", "\n", s, flags=re.IGNORECASE)
    t = re.sub(r"</p\s*>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[ \t\u3000]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()

def extract_skus_generic(subject: str, body_text: str) -> list[str]:
    skus = set()
    haystacks = []
    if subject:
        haystacks.append(("SUBJECT", subject))
    if body_text:
        haystacks.append(("BODY", body_text))
    for where, text in haystacks:
        for pat in ANCHOR_PATTERNS:
            for m in re.finditer(pat, text, flags=re.IGNORECASE):
                sku = (m.group(1) or "").strip()
                if sku and (" " not in sku) and ("\u3000" not in sku):
                    skus.add(sku)
    return list(skus)

def looks_like_rakuma(from_addr: str) -> bool:
    if not from_addr:
        return False
    s = from_addr.lower()
    return ("fril.jp" in s) or ("rakuma" in s)

def looks_like_amazon(from_addr: str) -> bool:
    return bool(from_addr and "amazon.co.jp" in from_addr.lower())

def looks_like_mercari(from_addr: str) -> bool:
    return bool(from_addr and ("mercari-shops.com" in from_addr.lower() or "mercari" in from_addr.lower()))

# =====================================================
# ログ設定
# =====================================================
# 現在地: src/mail_watcher/parsing/extractor.py
# → 4階層上がる: parsing → mail_watcher → src → mail_watcher
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

# 共通ディレクトリ
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# ディレクトリを保証
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ログファイル
LOG_PATH = os.path.join(LOG_DIR, "extract.log")

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} | {msg}\n")
    print(msg)

def main():
    db_path = get_db_path()

    # SQLite接続（ロック対策を強化）
    conn = sqlite3.connect(db_path, timeout=10)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")       # 同時アクセス許可モード
    cur.execute("PRAGMA busy_timeout = 10000;")   # 最大10秒リトライ

    cur.execute("""
        SELECT id, from_addr, subject, body_plain, profile, provider,
               message_id, date_utc, content_hash
        FROM emails
        WHERE status='unprocessed'
    """)
    mails = cur.fetchall()

    log(f"=== SKU抽出・在庫更新 開始 ===")
    if not mails:
        log("⚠️ 抽出対象のメールがありません（unprocessed=0）")
        conn.close()
        return

    for id_, from_addr, subject, body_raw, profile, provider, message_id, date_utc, content_hash in mails:
        body = strip_html_to_text(body_raw or "")
        subject = subject or ""
        sku_list = []

        # メール種別で分岐
        if looks_like_amazon(from_addr):
            sku_list = extract_skus_generic(subject, body)
        elif looks_like_mercari(from_addr):
            sku_list = extract_skus_generic(subject, body)
        elif looks_like_rakuma(from_addr):
            sku_list = re.findall(RAKUMA_ORDER_ID_PATTERN, body)
            if sku_list:
                log(f"🟣 ID {id_} | RAKUMA オーダーID記録: {', '.join(sku_list)} (SKU未検出想定)")
                cur.execute("UPDATE emails SET status='sku_missing' WHERE id=?", (id_,))
                conn.commit()
                continue

        # --- SKU抽出結果をDB登録 ---
        if sku_list:
            now = datetime.datetime.utcnow().isoformat()

            # 複数SKUを email_skus に登録
            for sku in sku_list:
                log(f"✅ ID {id_} | FROM: {from_addr} | SUBJECT: {subject[:80]} | SKU検出: {sku}")
                cur.execute("""
                    INSERT INTO email_skus (email_id, sku, created_at)
                    VALUES (?, ?, ?)
                """, (id_, sku, now))

            # 代表SKUをemailsテーブルに格納
            first_sku = sku_list[0]
            cur.execute(
                "UPDATE emails SET sku=?, status='unprocessed', updated_at=? WHERE id=?",
                (first_sku, now, id_)
            )

        else:
            log(f"⚠️ ID {id_} | FROM: {from_addr} | SUBJECT: {subject[:80]} | SKU抽出失敗")
            cur.execute(
                "UPDATE emails SET status='sku_missing', updated_at=? WHERE id=?",
                (datetime.datetime.utcnow().isoformat(), id_)
            )

        conn.commit()  # ← 各メールごとに確定

    # ✅ すべてのメール処理が終わった後で閉じる
    conn.close()
    log(f"=== SKU抽出・在庫更新 完了 ===")

if __name__ == "__main__":
    main()
