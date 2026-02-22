import csv
import os

def load_config(profile="main"):
    """
    config/config.csv を自動判別で読み込み、辞書で返す。
    - 縦持ち形式（constant/data）にも対応
    - 横持ち形式（PROFILE列あり）にも対応
    - カレントディレクトリや実行モジュールに依存しない（完全自動検出）
    """

    # --- mail_watcher 直下の config フォルダを自動探索 ---
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = None
    path = current_dir

    while True:
        candidate = os.path.join(path, "config", "config.csv")
        if os.path.exists(candidate):
            project_root = path
            break
        parent = os.path.dirname(path)
        if parent == path:
            break  # ルートまで来たら終了
        path = parent

    if project_root is None:
        raise FileNotFoundError(
            "設定ファイルが見つかりません。mail_watcher/config/config.csv が存在するか確認してください。"
        )

    config_path = os.path.join(project_root, "config", "config.csv")

    # --- ファイル形式の自動判定 ---
    with open(config_path, encoding="cp932") as f:
        reader = csv.reader(f)
        headers = next(reader)

    # ---------------------------------------------
    # パターン1: 縦持ち（constant/data）
    # ---------------------------------------------
    if "constant" in headers and "data" in headers:
        config = {}
        with open(config_path, encoding="cp932") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row.get("constant", "").strip()
                val = row.get("data", "").strip()
                if key:
                    config[key] = val
        return config

    # ---------------------------------------------
    # パターン2: 横持ち（PROFILE列あり）
    # ---------------------------------------------
    elif "PROFILE" in headers:
        with open(config_path, encoding="cp932") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("PROFILE", "").strip() == profile:
                    return row
        raise ValueError(f"PROFILE={profile} の設定が見つかりませんでした")

    # ---------------------------------------------
    # パターン3: その他（未知形式）
    # ---------------------------------------------
    else:
        raise ValueError(f"config.csv の列構成が不明です: {headers}")
