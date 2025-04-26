"""アプリケーションのロギング設定を管理するモジュール。

このモジュールは、アプリケーション全体のロギング設定を管理します。
YAMLファイルベースの詳細設定と、フォールバック用の基本設定の両方をサポートします。

主な機能:
    - YAMLファイルからのロギング設定の読み込み
    - ログディレクトリの自動作成
    - ログローテーション設定
    - コンソールとファイルの両方への出力

Note:
    設定ファイルは config/logging.yaml に配置する必要があります。
    ファイルが存在しない場合は、基本的なロギング設定が使用されます。
"""

import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml


def setup_logging() -> None:
    """アプリケーションのロギング設定を初期化します。

    以下の順序で設定を行います：
        1. APP_BASE_DIRまたはデフォルトパスからの設定ファイルの読み込み
        2. ログディレクトリの作成
        3. YAMLファイルからの設定の適用、または基本設定の使用

    基本設定（YAML設定ファイルが存在しない場合）:
        - ログレベル: INFO
        - フォーマット: タイムスタンプ、モジュール名、ログレベル、メッセージ
        - 出力先: コンソールとローテーティングファイル
        - ファイルローテーション: 5MB、5世代まで保持

    Raises:
        OSError: ログディレクトリの作成に失敗した場合
        yaml.YAMLError: YAML設定ファイルの解析に失敗した場合
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
