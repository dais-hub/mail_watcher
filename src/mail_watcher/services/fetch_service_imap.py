import os
import csv
import imaplib
import email
import hashlib
import datetime
import sqlite3
from email.header import decode_header, make_header
from mail_watcher.config_loader import load_config
from ..db.models import get_db_path

# =====================================================
# ログ設定
# =====================================================
# 現在地: src/mail_watcher/services/fetch_service_imap.py
# → 4階層上がる: services → mail_watcher → src → mail_watcher
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

# 共通ディレクトリ
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# パスを保証
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ログファイル
LOG_FILE = os.path.join(LOG_DIR, "fetch_imap.log")

def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# =====================================================
# 安全なDB接続関数（WAL + timeout + busy_timeout）
# =====================================================
def get_safe_connection(db_path):
    conn = sqlite3.connect(db_path, timeout=10)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA busy_timeout = 10000;")
    conn.commit()
    return conn


# =====================================================
# 設定読み込み
# =====================================================
def load_config_csv():
    """
    config/config.csv を読み込み、B列（キー）とC列（値）を辞書化。
    mail_watcher/config_loader の自動パス解決を利用して安全に取得。
    """
    try:
        # まず config_loader で安全にファイルパスを取得
        base_conf = load_config()
    except Exception as e:
        raise FileNotFoundError(f"設定ファイルの読み込みに失敗しました: {e}")

    # === ここから従来処理を維持（B列・C列対応） ===
    import csv
    import os

    # config_loader が見つけた config.csv のパスを再利用
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "../../../config/config.csv"
    )
    config_path = os.path.normpath(config_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.csvが見つかりません: {config_path}")

    conf = {}
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3 and row[1] and not row[1].startswith("#"):
                    conf[row[1].strip()] = row[2].strip() if len(row) > 2 else ""
    except UnicodeDecodeError:
        with open(config_path, "r", encoding="cp932") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3 and row[1] and not row[1].startswith("#"):
                    conf[row[1].strip()] = row[2].strip() if len(row) > 2 else ""

    return conf


# =====================================================
# IMAP接続とメール取得処理
# =====================================================
def connect_imap(host, user, password):
    """IMAP接続を確立（SSL→StartTLS→平文IMAPの順で試行）"""
    try:
        imap = imaplib.IMAP4_SSL(host, 993)
        imap.login(user, password)
        log(f"✅ IMAP SSL接続成功: {host}")
        return imap
    except Exception as e_ssl:
        log(f"⚠️ SSL接続失敗 ({e_ssl}) → StartTLS試行")

    try:
        imap = imaplib.IMAP4(host, 143)
        imap.starttls()
        imap.login(user, password)
        log(f"✅ IMAP StartTLS接続成功: {host}")
        return imap
    except Exception as e_tls:
        log(f"⚠️ StartTLS失敗 ({e_tls}) → 通常IMAP試行")

    try:
        imap = imaplib.IMAP4(host, 143)
        imap.login(user, password)
        log(f"✅ 通常IMAP接続成功: {host}")
        return imap
    except Exception as e_plain:
        log(f"❌ IMAP接続失敗: {host} ({e_plain})")
        return None


def decode_mime(text):
    if not text:
        return ""
    try:
        return str(make_header(decode_header(text)))
    except Exception:
        return text


def get_body(msg):
    """text/plain本文を優先的に取得"""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                except Exception:
                    continue
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/html":
                try:
                    html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                    return html
                except Exception:
                    continue
    else:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
    return ""


def fetch_and_store(config, label, host, user, password, from_filter):
    """指定されたFROMフィルタのメールを取得してDB登録"""
    imap = connect_imap(host, user, password)
    if not imap:
        return

    db_path = get_db_path(config)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_safe_connection(db_path)
    cur = conn.cursor()

    since = (datetime.date.today() - datetime.timedelta(days=3)).strftime("%d-%b-%Y")
    imap.select("INBOX")
    typ, data = imap.search(None, f'(SINCE "{since}" FROM "{from_filter}")')

    if typ != "OK":
        log(f"⚠️ {label}: メール検索に失敗しました。")
        imap.logout()
        return

    uids = data[0].split()
    log(f"📬 {label}: {len(uids)}件ヒット ({from_filter})")

    new_count = 0
    for uid in uids:
        typ, msg_data = imap.fetch(uid, "(RFC822)")
        if typ != "OK":
            continue
        msg = email.message_from_bytes(msg_data[0][1])

        subject = decode_mime(msg.get("Subject", ""))
        from_addr = decode_mime(msg.get("From", ""))
        date_utc = msg.get("Date", "")
        message_id = msg.get("Message-ID", f"uid-{uid.decode()}")
        body = get_body(msg)
        if not body:
            continue

        h = hashlib.sha1(body.encode("utf-8")).hexdigest()

        cur.execute("SELECT COUNT(*) FROM emails WHERE message_id=? OR content_hash=?", (message_id, h))
        if cur.fetchone()[0] > 0:
            continue

        now = datetime.datetime.utcnow().isoformat()
        cur.execute("""
            INSERT INTO emails (
                profile, provider, message_id, date_utc,
                from_addr, subject, body_plain, status,
                content_hash, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            label.lower(),
            "imap",
            message_id,
            date_utc,
            from_addr,
            subject,
            body,
            "unprocessed",
            h,
            now,
            now
        ))
        new_count += 1

    conn.commit()
    conn.close()
    imap.logout()
    log(f"✅ {label}: 新規 {new_count} 件をDBに登録完了。")


def main():
    config = load_config_csv()
    db_path = get_db_path(config)

    if not os.path.exists(db_path):
        log(f"⚙️ DBが存在しないため初期化します: {db_path}")
        from ..db.init_db import init_db
        init_db()
    else:
        log(f"✅ DB確認済み: {db_path}")

    if config.get("SWITCH_AMAZON", "1") == "1":
        fetch_and_store(config,
                        "Amazon",
                        config.get("IMAP_HOST_AMAZON", ""),
                        config.get("IMAP_USER_AMAZON", ""),
                        config.get("IMAP_PASS_AMAZON", ""),
                        config.get("FROM_FILTER_AMAZON", "seller-notification@amazon.co.jp"))

    if config.get("SWITCH_MERCARI", "1") == "1":
        fetch_and_store(config,
                        "Mercari",
                        config.get("IMAP_HOST_MERCARI", config.get("IMAP_HOST_AMAZON", "")),
                        config.get("IMAP_USER_MERCARI", ""),
                        config.get("IMAP_PASS_MERCARI", ""),
                        config.get("FROM_FILTER_MERCARI", "no-reply@mercari-shops.com"))

    if config.get("SWITCH_RAKUMA", "1") == "1":
        fetch_and_store(config,
                        "Rakuma",
                        config.get("IMAP_HOST_RAKUMA", config.get("IMAP_HOST_AMAZON", "")),
                        config.get("IMAP_USER_RAKUMA", ""),
                        config.get("IMAP_PASS_RAKUMA", ""),
                        config.get("FROM_FILTER_RAKUMA", "notice@rakuma.rakuten.co.jp"))

    log("=== IMAP受信処理完了 ===")


if __name__ == "__main__":
    main()
