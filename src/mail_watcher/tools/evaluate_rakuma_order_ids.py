import argparse
import csv
import datetime
import email
import imaplib
import os
from email.header import decode_header, make_header

from mail_watcher.config_loader import load_config
from mail_watcher.parsing.extractor import extract_rakuma_order_ids, is_rakuma_trigger_subject


def decode_mime(text: str) -> str:
    if not text:
        return ""
    try:
        return str(make_header(decode_header(text)))
    except Exception:
        return text


def get_body(msg) -> str:
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
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                except Exception:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


def connect_imap(host: str, user: str, password: str):
    try:
        imap = imaplib.IMAP4_SSL(host, 993)
        imap.login(user, password)
        return imap
    except Exception:
        pass

    try:
        imap = imaplib.IMAP4(host, 143)
        imap.starttls()
        imap.login(user, password)
        return imap
    except Exception:
        pass

    imap = imaplib.IMAP4(host, 143)
    imap.login(user, password)
    return imap


def main():
    parser = argparse.ArgumentParser(
        description="過去N日のラクマ受注メールからオーダーIDを抽出してCSVに記録"
    )
    parser.add_argument("--days", type=int, default=2, help="検索対象日数（デフォルト: 2）")
    parser.add_argument("--from-filter", default="noreply@fril.jp", help="FROMフィルタ")
    parser.add_argument("--subject", default="[楽天ラクマ] 決済完了のお知らせ", help="件名トリガー")
    parser.add_argument("--output", default="", help="出力CSVパス（未指定時は logs 配下に自動生成）")
    args = parser.parse_args()

    conf = load_config()
    host = conf.get("IMAP_HOST_RAKUMA", conf.get("IMAP_HOST_AMAZON", ""))
    user = conf.get("IMAP_USER_RAKUMA", "")
    password = conf.get("IMAP_PASS_RAKUMA", "")

    if not host or not user or not password:
        raise RuntimeError("IMAP_HOST_RAKUMA / IMAP_USER_RAKUMA / IMAP_PASS_RAKUMA が設定されていません")

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    if args.output:
        output_path = os.path.abspath(args.output)
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(logs_dir, f"rakuma_order_id_eval_{ts}.csv")

    since = (datetime.date.today() - datetime.timedelta(days=args.days)).strftime("%d-%b-%Y")

    imap = connect_imap(host, user, password)
    imap.select("INBOX")

    criteria = f'(SINCE "{since}" FROM "{args.from_filter}")'
    typ, data = imap.search(None, criteria)
    if typ != "OK":
        imap.logout()
        raise RuntimeError(f"IMAP検索失敗: {criteria}")

    uids = data[0].split()
    rows = []

    for uid in uids:
        typ, msg_data = imap.fetch(uid, "(RFC822)")
        if typ != "OK":
            continue

        msg = email.message_from_bytes(msg_data[0][1])
        subject = decode_mime(msg.get("Subject", ""))
        from_addr = decode_mime(msg.get("From", ""))
        date_hdr = msg.get("Date", "")
        message_id = msg.get("Message-ID", f"uid-{uid.decode()}")

        if args.subject not in subject:
            continue
        if not is_rakuma_trigger_subject(subject):
            continue

        body = get_body(msg)
        order_ids = extract_rakuma_order_ids(subject, body)
        if not order_ids:
            rows.append({
                "uid": uid.decode(),
                "message_id": message_id,
                "date": date_hdr,
                "from": from_addr,
                "subject": subject,
                "order_id": "",
                "result": "order_id_not_found",
            })
            continue

        for oid in sorted(set(order_ids)):
            rows.append({
                "uid": uid.decode(),
                "message_id": message_id,
                "date": date_hdr,
                "from": from_addr,
                "subject": subject,
                "order_id": oid,
                "result": "ok",
            })

    imap.logout()

    fieldnames = ["uid", "message_id", "date", "from", "subject", "order_id", "result"]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    ok_count = sum(1 for r in rows if r["result"] == "ok")
    ng_count = sum(1 for r in rows if r["result"] != "ok")

    print("=== ラクマ受注メール評価完了 ===")
    print(f"対象条件: days={args.days}, from={args.from_filter}, subject={args.subject}")
    print(f"抽出成功件数: {ok_count}")
    print(f"抽出失敗件数: {ng_count}")
    print(f"出力CSV: {output_path}")


if __name__ == "__main__":
    main()
