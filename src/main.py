"""MoneyForwardスクレイピングのメインモジュール。

このモジュールは、MoneyForwardからの家計データスクレイピングとスプレッドシートへの同期を制御します。

主な機能:
    - MoneyForwardからの家計データ自動取得
    - 取得したデータのスプレッドシートへの同期
    - ロギングによる実行状態の監視

Note:
    実行には適切な認証情報とアクセス権限が必要です。
    設定は config/ ディレクトリ下の各設定ファイルで管理されています。

"""

import logging

from config.logging_config import setup_logging
from exceptions.custom_exceptions import MoneyForwardError
from scraper.scraper import MoneyForwardScraper
from spreadsheet.sync import SpreadsheetSync

# ロギング設定
setup_logging()
logger = logging.getLogger(__name__)


def run_scraping() -> None:
    """MoneyForwardのスクレイピングとスプレッドシート同期を実行します。

    この関数は以下の処理を順次実行します：
        1. MoneyForwardへのログインとデータ取得
        2. 取得したデータのスプレッドシートへの同期

    Returns:
        None

    Raises:
        MoneyForwardError: スクレイピング処理で発生したエラー
        Exception: その他の予期せぬエラー

    """
    try:
        # スクレイピングの実行
        logger.info("スクレイピングを開始します。")
        scraper = MoneyForwardScraper()
        scraper.scrape()
        logger.info("スクレイピングが完了しました。")

        # スプレッドシートの同期
        logger.info("スプレッドシートの同期を開始します。")
        sync = SpreadsheetSync()
        sync.sync()
        logger.info("スプレッドシートの同期が完了しました。")

    except MoneyForwardError as e:
        logger.error("処理中にエラーが発生しました: %s", e)
    except Exception as e:
        logger.error("予期せぬエラーが発生しました: %s", e)


if __name__ == "__main__":
    # スクレイピング処理を実行
    run_scraping()
