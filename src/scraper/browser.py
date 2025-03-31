"""ブラウザ操作モジュール。"""

import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional, TypeVar

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
from exceptions.custom_exceptions import AuthenticationError, ScrapingError

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ScrapingResult:
    """スクレイピング結果を格納するデータクラス。"""

    links: List[str]
    cookies: List[dict]


class BrowserManager:
    """ブラウザ操作を管理するクラス。"""

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
        """ChromeDriverの設定を初期化。"""
        self.driver: Optional[WebDriver] = None
        self.timeout = settings.moneyforward.selenium.timeout
        self.retry_count = settings.moneyforward.selenium.retry_count

    def __enter__(self) -> "BrowserManager":
        """コンテキストマネージャーのエントリーポイント。"""
        self.setup_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """コンテキストマネージャーの終了処理。"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def setup_driver(self) -> None:
        """ChromeDriverを設定。"""
        chrome_options = Options()
        # ChromeDriverのパス設定
        chrome_driver_path = os.getenv(
            "CHROME_DRIVER_PATH", settings.paths.chrome_driver
        )
        if not os.path.exists(chrome_driver_path):
            raise ScrapingError(f"ChromeDriverが見つかりません: {chrome_driver_path}")

        # ChromeバイナリのPATH設定
        chrome_path = os.getenv("CHROME_PATH", "/usr/bin/chromium")
        if not os.path.exists(chrome_path):
            raise ScrapingError(f"Chromeバイナリが見つかりません: {chrome_path}")
        chrome_options.binary_location = chrome_path

        # ヘッドレスモードとセキュリティ設定
        chrome_options.add_argument("--headless=new")  # 新しいヘッドレスモード
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-gpu")  # GPUを無効化
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--disable-extensions")  # 拡張機能を無効化
        chrome_options.add_argument("--disable-infobars")  # 情報バーを無効化
        chrome_options.add_argument(
            "--disable-popup-blocking"
        )  # ポップアップブロックを無効化
        chrome_options.add_argument(
            "--disable-application-cache"
        )  # アプリケーションキャッシュを無効化
        chrome_options.add_argument("--disable-web-security")  # セキュリティを無効化
        chrome_options.add_argument(
            "--allow-running-insecure-content"
        )  # 不正なコンテンツを許可
        chrome_options.add_argument("--lang=ja")  # 日本語に設定
        chrome_options.add_argument("--window-size=1920x1080")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        )

        # ダウンロード設定
        prefs = {
            "profile.default_content_settings.popups": 0,
            "download.default_directory": settings.paths.downloads,
            "safebrowsing.enabled": "false",
        }
        chrome_options.add_experimental_option("prefs", prefs)

        try:
            # ChromeDriverを直接設定
            service = Service(executable_path=chrome_driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except WebDriverException as e:
            raise ScrapingError(f"WebDriverの初期化に失敗しました: {e}") from e

    def wait_and_find_element(
        self, by: By, value: str, timeout: Optional[int] = None
    ) -> WebElement:
        """要素が見つかるまで待機して取得。

        Args:
            by: 検索方法。
            value: 検索値。
            timeout: タイムアウト時間（秒）。

        Returns:
            検索された要素。

        Raises:
            ScrapingError: 要素が見つからない場合。
        """
        if not self.driver:
            raise ScrapingError("WebDriverが初期化されていません。")

        timeout = timeout or self.timeout
        try:
            element: Optional[WebElement] = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((self._by_mapping[by], value))  # type: ignore
            )
            if not element:
                raise ScrapingError(f"要素が見つかりませんでした: {by}={value}")
            return element
        except TimeoutException as e:
            raise ScrapingError(f"要素が見つかりませんでした: {by}={value}") from e
        except KeyError as e:
            raise ScrapingError(f"無効な検索方法です: {by}") from e

    def retry_operation(self, operation, *args, **kwargs):
        """操作を指定回数リトライ。

        Args:
            operation: リトライする操作の関数。
            *args: 操作関数の位置引数。
            **kwargs: 操作関数のキーワード引数。

        Returns:
            操作の結果。

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

    def login(self, email: str, password: str) -> None:
        """MoneyForwardにログイン。

        Args:
            email: ログイン用メールアドレス。
            password: ログイン用パスワード。

        Raises:
            AuthenticationError: ログインに失敗した場合。
        """
        if not self.driver:
            raise ScrapingError("WebDriverが初期化されていません。")

        url = f"{settings.moneyforward.base_url}{settings.moneyforward.endpoints.login}"
        try:
            self.driver.get(url)
            logger.info("MoneyForwardログインページにアクセスしています: %s", url)

            # メールアドレス入力
            email_input = self.wait_and_find_element(By.NAME, "mfid_user[email]")  # type: ignore
            email_input.send_keys(email)
            email_input.submit()

            # パスワード入力
            password_input = self.wait_and_find_element(By.NAME, "mfid_user[password]")  # type: ignore
            password_input.send_keys(password)
            password_input.submit()

            # ログイン成功の確認
            self.wait_and_find_element(By.CLASS_NAME, "accounts")  # type: ignore
            logger.info("MoneyForwardへのログインが完了しました。ユーザー: %s", email)

        except (ScrapingError, TimeoutException) as e:
            raise AuthenticationError("ログインに失敗しました。") from e

    def get_links_for_download(self, page_url: str) -> List[str]:
        """指定されたページからダウンロードリンクを抽出。

        Args:
            page_url: ダウンロードリンクを抽出するページのURL。

        Returns:
            List[str]: 抽出されたダウンロードリンクのリスト。

        Raises:
            ScrapingError: リンクの抽出に失敗した場合。
        """
        if not self.driver:
            raise ScrapingError("WebDriverが初期化されていません。")

        logger.info("アカウントページからダウンロードリンクの抽出を開始: %s", page_url)
        self.driver.get(page_url)

        try:
            # アカウントテーブルを取得
            accounts_table = self.wait_and_find_element(By.CLASS_NAME, "accounts")  # type: ignore

            try:
                # データテーブルを取得
                table = accounts_table.find_element(
                    By.CSS_SELECTOR, ".table.table-striped"
                )
            except NoSuchElementException as e:
                raise ScrapingError(f"データテーブルの取得に失敗しました: {e}") from e

            # テーブルの行を取得
            try:
                rows = table.find_elements(By.TAG_NAME, "tr")
            except NoSuchElementException as e:
                raise ScrapingError(
                    f"テーブルの行データの抽出に失敗しました: {e}"
                ) from e

            # 空のテーブルをチェック
            if len(rows) <= 1:  # ヘッダー行のみ、またはデータなし
                logger.warning("テーブルにデータがありません")
                return []

            # ヘッダー行を除外
            rows = rows[1:]

            links = []
            for row in rows:
                try:
                    # td要素を探して、その中のaタグを取得
                    cell = row.find_element(By.TAG_NAME, "td")
                    link_element = cell.find_element(By.TAG_NAME, "a")
                    link = link_element.get_attribute("href")
                    if link:
                        links.append(link)
                        logger.info("リンクを抽出しました: %s", link)
                except (NoSuchElementException, StaleElementReferenceException) as e:
                    logger.warning(
                        "アカウントリンクの抽出に失敗しました: %s（現在の抽出済みリンク数: %d）",
                        e,
                        len(links),
                    )
                    continue

            logger.info(
                "リンクの抽出が完了しました。抽出されたリンク数: %d", len(links)
            )
            return links

        except Exception as e:
            raise ScrapingError(f"ダウンロードリンクの抽出に失敗しました: {e}") from e

    def get_cookies(self) -> List[dict]:
        """現在のセッションのクッキー情報を取得。

        Returns:
            List[dict]: クッキー情報のリスト。

        Raises:
            ScrapingError: クッキーの取得に失敗した場合。
        """
        if not self.driver:
            raise ScrapingError("WebDriverが初期化されていません。")

        try:
            return self.driver.get_cookies()
        except WebDriverException as e:
            raise ScrapingError(f"クッキーの取得に失敗しました: {e}") from e
