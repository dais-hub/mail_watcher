# src/mail_watcher/cli.py
import argparse
from .config_loader import load_config
from .db.models import init_db
from .services.fetch_service import import_emails

def main():
    parser = argparse.ArgumentParser(description="mail_watcher CLI")
    parser.add_argument("command", choices=["init", "import-emails"])
    parser.add_argument("--profile", default="main")
    args = parser.parse_args()

    config = load_config(args.profile)

    if args.command == "init":
        init_db(config)

    elif args.command == "import-emails":
        import_emails(config)

if __name__ == "__main__":
    main()
