"""ロギング設定管理モジュール。"""

import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml


def setup_logging() -> None:
    """
    ロギング設定を行う。

    YAMLファイルからロギング設定を読み込み、適用する。
    ファイルが存在しない場合は基本的な設定を使用する。
    """
    base_dir = Path(os.getenv("APP_BASE_DIR", "/app"))
    config_path = base_dir / "config/logging.yaml"
    log_dir = base_dir / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            logging.config.dictConfig(config)
    else:
        # 基本的なロギング設定
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                RotatingFileHandler(
                    filename=str(log_dir / "app.log"),
                    maxBytes=5 * 1024 * 1024,  # 5MB
                    backupCount=5,
                    encoding="utf-8",
                ),
            ],
        )
        logging.warning("ロギング設定ファイルが見つかりません: %s", config_path)
