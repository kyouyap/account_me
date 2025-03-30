"""MoneyForwardスクレイピングとBigQueryロードを行うメインモジュール。"""

import logging
import time
from pathlib import Path

from config.logging_config import setup_logging
from exceptions.custom_exceptions import MoneyForwardError
from load.bigquery_loader import BigQueryLoader
from scraper.scraper import MoneyForwardScraper

# ロギング設定
setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    """メイン関数。"""
    try:
        # 起動待機（Seleniumコンテナの起動を待つ）
        logger.info("Seleniumコンテナの起動を待機中...")
        time.sleep(10)

        # スクレイピングの実行
        logger.info("スクレイピングを開始します。")
        scraper = MoneyForwardScraper()
        scraper.scrape()
        logger.info("スクレイピングが完了しました。")

        # BigQueryへのデータロード
        logger.info("BigQueryへのデータロードを開始します。")
        loader = BigQueryLoader()

        # 取引データのロード
        detail_file = Path("outputs/aggregated_files/detail/detail_latest.csv")
        if detail_file.exists():
            if loader.load_transactions(detail_file):
                logger.info("取引データのロードが完了しました。")
            else:
                logger.error("取引データのロードに失敗しました。")

        # 資産データのロード
        assets_file = Path("outputs/aggregated_files/assets/assets_latest.csv")
        if assets_file.exists():
            if loader.load_assets(assets_file):
                logger.info("資産データのロードが完了しました。")
            else:
                logger.error("資産データのロードに失敗しました。")

    except MoneyForwardError as e:
        logger.error("処理中にエラーが発生しました: %s", e)
        raise
    except Exception as e:
        logger.error("予期せぬエラーが発生しました: %s", e)
        raise


if __name__ == "__main__":
    main()
