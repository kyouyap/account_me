"""Selenium操作の基底クラスモジュール。"""

import logging
import os
import time
from typing import TypeVar, Optional

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import settings
from exceptions.custom_exceptions import ScrapingError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseSeleniumManager:
    """Selenium操作の基底クラス。"""

    _by_mapping = {
        By.ID: "id",
        By.XPATH: "xpath",
        By.NAME: "name",
        By.CLASS_NAME: "class name",
        By.CSS_SELECTOR: "css selector",
        By.TAG_NAME: "tag name",
        By.LINK_TEXT: "link text",
        By.PARTIAL_LINK_TEXT: "partial link text",
    }

    def __init__(self) -> None:
        """初期化。"""
        self.driver: Optional[WebDriver] = None
        self.timeout = settings.moneyforward.selenium.timeout
        self.retry_count = settings.moneyforward.selenium.retry_count

    def __enter__(self) -> "BaseSeleniumManager":
        """コンテキストマネージャのエントリーポイント。"""
        self.setup_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """コンテキストマネージャの終了処理。"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def setup_driver(self) -> None:
        """ChromeDriverを設定。"""
        logger.info("ブラウザドライバの設定を開始")
        chrome_options = Options()

        # ChromeDriverのパス設定
        chrome_driver_path = os.getenv(
            "CHROME_DRIVER_PATH", settings.paths.chrome_driver
        )
        logger.info("ChromeDriverパス: %s", chrome_driver_path)
        if not os.path.exists(chrome_driver_path):
            logger.error("ChromeDriverが見つかりません: %s", chrome_driver_path)
            raise ScrapingError(f"ChromeDriverが見つかりません: {chrome_driver_path}")

        # ChromeバイナリのPATH設定
        chrome_path = os.getenv("CHROME_PATH", "/usr/bin/chromium")
        logger.info("Chromeバイナリパス: %s", chrome_path)
        if not os.path.exists(chrome_path):
            logger.error("Chromeバイナリが見つかりません: %s", chrome_path)
            raise ScrapingError(f"Chromeバイナリが見つかりません: {chrome_path}")
        chrome_options.binary_location = chrome_path
        logger.info("Chromeバイナリの設定が完了")

        # ブラウザオプションの設定
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-application-cache")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--lang=ja")
        chrome_options.add_argument("--window-size=1920x1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        )

        # ダウンロード設定
        prefs = {
            "profile.default_content_settings.popups": 0,
            "download.default_directory": settings.paths.downloads,
            "safebrowsing.enabled": "false",
        }
        chrome_options.add_experimental_option("prefs", prefs)

        try:
            logger.info("ChromeDriverサービスを初期化")
            service = Service(executable_path=chrome_driver_path)

            logger.info("WebDriverを初期化")
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("WebDriverの初期化が完了")

        except WebDriverException as e:
            logger.error("WebDriverの初期化に失敗: %s", e, exc_info=True)
            raise ScrapingError(f"WebDriverの初期化に失敗しました: {e}") from e
        except Exception as e:
            logger.error("予期せぬエラーが発生: %s", e, exc_info=True)
            raise ScrapingError(f"ブラウザの設定中に予期せぬエラーが発生: {e}") from e

    def wait_and_find_element(
        self, by: By | str, value: str, timeout: Optional[int] = None
    ) -> WebElement:
        """要素が見つかるまで待機して取得。

        Args:
            by: 検索方法。
            value: 検索値。
            timeout: タイムアウト時間（秒）。

        Returns:
            WebElement: 検索された要素。

        Raises:
            ScrapingError: 要素が見つからない場合、またはWebDriverが未初期化の場合。
        """
        if not self.driver:
            raise ScrapingError("WebDriverが初期化されていません。")

        timeout = timeout or self.timeout
        logger.info("要素の検索を開始: %s=%s（タイムアウト: %d秒）", by, value, timeout)
        try:
            logger.debug("要素の待機を開始")
            element: Optional[WebElement] = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((self._by_mapping[by], value))  # type: ignore
            )
            if not element:
                logger.error("要素が見つかりませんでした: %s=%s", by, value)
                raise ScrapingError(f"要素が見つかりませんでした: {by}={value}")
            logger.info("要素が見つかりました: %s=%s", by, value)
            return element
        except TimeoutException as e:
            logger.error("要素の待機がタイムアウト: %s=%s", by, value)
            if self.driver:
                logger.debug("現在のページソース: %s", self.driver.page_source)
            raise ScrapingError(f"要素が見つかりませんでした: {by}={value}") from e
        except KeyError as e:
            logger.error("無効な検索方法が指定されました: %s", by)
            raise ScrapingError(f"無効な検索方法です: {by}") from e

    def retry_operation(self, operation, *args, **kwargs):
        """操作を指定回数リトライ。

        Args:
            operation: リトライする操作の関数。
            *args: 操作関数の位置引数。
            **kwargs: 操作関数のキーワード引数。

        Returns:
            Any: 操作の結果。

        Raises:
            ScrapingError: すべてのリトライが失敗した場合。
        """
        last_error = None
        for attempt in range(self.retry_count):
            try:
                return operation(*args, **kwargs)
            except (NoSuchElementException, StaleElementReferenceException) as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    logger.warning(
                        "要素操作が失敗しました（リトライ %d/%d）: 要素 '%s=%s' に対する操作に失敗: %s",
                        attempt + 1,
                        self.retry_count,
                        args[0] if args else "unknown",
                        args[1] if len(args) > 1 else "unknown",
                        e,
                    )
                    time.sleep(1)
                    continue
        raise ScrapingError(f"操作が{self.retry_count}回失敗しました: {last_error}")
