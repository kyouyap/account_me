"""MoneyForwardスクレイピングメインモジュール。"""

import logging
import time
from config.logging_config import setup_logging
from exceptions.custom_exceptions import MoneyForwardError
from scraper.scraper import MoneyForwardScraper
from spreadsheet.sync import SpreadsheetSync


# ロギング設定
setup_logging()
logger = logging.getLogger(__name__)


def run_scraping() -> None:
    """スクレイピング処理を実行する。"""
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