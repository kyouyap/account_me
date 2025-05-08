"""Seleniumを使用したブラウザ自動操作を管理するモジュール。

このモジュールは、MoneyForwardウェブサイトへのアクセスと操作を自動化します。
ChromeDriverを使用したヘッドレスブラウザの設定、ページ要素の待機と操作、
認証処理など、スクレイピングに必要な基本機能を提供します。

主な機能:
    - ヘッドレスChromeブラウザの設定と管理
    - ページ要素の待機と検索
    - MoneyForwardへのログイン処理（2段階認証対応）
    - ダウンロードリンクの抽出
    - セッション管理

Note:
    - ChromeDriverのパスが正しく設定されている必要があります
    - Gmail APIを使用して2段階認証コードを取得します
    - 設定はsettingsモジュールから読み込まれます

"""

import logging
import os
import time
from dataclasses import dataclass
from typing import TypeVar

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
from exceptions.custom_exceptions import (
    AuthenticationError,
    GmailApiError,
    ScrapingError,
    VerificationCodeError,
)
from scraper.gmail_client import GmailClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ScrapingResult:
    """スクレイピング結果を格納するデータクラス。

    Attributes:
        links (List[str]): 抽出されたダウンロードリンクのリスト
        cookies (List[dict]): セッションのクッキー情報

    """

    links: list[str]
    cookies: list[dict]


class BrowserManager:
    """ブラウザ操作を管理するクラス。

    このクラスは、Seleniumを使用したブラウザ操作の全般を管理します。
    コンテキストマネージャとして実装されており、with文での使用を想定しています。

    Attributes:
        driver (Optional[WebDriver]): Seleniumのウェブドライバインスタンス
        timeout (int): 要素待機のタイムアウト時間（秒）
        retry_count (int): 操作失敗時のリトライ回数

    使用例:
        ```python
        with BrowserManager() as browser:
            browser.login(email, password)
            links = browser.get_links_for_download(target_url)
        ```

    """

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
        self.driver: WebDriver | None = None
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
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/58.0.3029.110 Safari/537.3"
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
        self, by: str, value: str, timeout: int | None = None
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
        logger.info("要素の検索を開始: %s=%s（タイムアウト: %d秒）", by, value, timeout)
        try:
            logger.debug("要素の待機を開始")
            element: WebElement | None = WebDriverWait(self.driver, timeout).until(
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
                        "要素操作が失敗しました（リトライ %d/%d）: "
                        "要素 '%s=%s' に対する操作に失敗: %s",
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
        """MoneyForwardにログインします。

        ログインフォームにメールアドレスとパスワードを入力し、必要に応じて
        2段階認証も処理します。2段階認証コードはGmail APIを使用して取得します。

        処理の流れ:
            1. ログインページにアクセス
            2. メールアドレスを入力
            3. パスワードを入力
            4. 2段階認証が必要な場合:
                - Gmail APIで認証コードを取得
                - 認証コードを入力
            5. ログイン成功を確認

        Args:
            email: ログイン用メールアドレス
            password: ログイン用パスワード

        Raises:
            AuthenticationError: 以下の場合に発生:
                - ログインフォームの要素が見つからない
                - 認証情報が無効
                - 2段階認証に失敗
                - その他のログイン処理エラー
            ScrapingError: WebDriverが初期化されていない場合

        """
        if not self.driver:
            raise ScrapingError("WebDriverが初期化されていません。")

        url = f"{settings.moneyforward.base_url}{settings.moneyforward.endpoints.login}"
        try:
            self.driver.get(url)
            logger.info("MoneyForwardログインページにアクセスしています: %s", url)

            # メールアドレス入力
            logger.info("メールアドレス入力フォームを探索中")
            email_input = self.wait_and_find_element(By.NAME, "mfid_user[email]")  # type: ignore
            logger.info("メールアドレスを入力: %s", email)
            email_input.send_keys(email)
            logger.info("メールアドレスフォームを送信")
            email_input.submit()
            logger.info("メールアドレス送信完了")

            # パスワード入力
            logger.info("パスワード入力フォームを探索中")
            password_input = self.wait_and_find_element(By.NAME, "mfid_user[password]")  # type: ignore
            logger.debug("パスワードを入力")
            password_input.send_keys(password)
            logger.info("パスワードフォームを送信")
            password_input.submit()
            logger.info("パスワード送信完了")
            logger.info("Gmail APIクライアントを初期化")
            gmail_client = GmailClient()
            self._handle_two_factor_authentication(gmail_client)

            # デバッグのためにpage_sourceを保存
            logger.info("現在のページソースを保存")
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            logger.info("ページソースの保存完了")

            # ログイン成功の確認
            logger.info("ログイン成功の確認を開始")
            self.wait_and_find_element(By.CLASS_NAME, "accounts")  # type: ignore
            logger.info("MoneyForwardへのログインが完了しました。ユーザー: %s", email)

        except TimeoutException as e:
            logger.error("要素待機中にタイムアウトが発生: %s", e)
            # デバッグのためにエラー時のページソースも保存
            if self.driver:
                with open("error_page.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                logger.info("エラー時のページソースを保存しました: error_page.html")
            raise AuthenticationError(
                "ログインフォームの要素が見つかりませんでした。"
            ) from e
        except ScrapingError as e:
            logger.error("スクレイピング中にエラーが発生: %s", e)
            # デバッグのためにエラー時のページソースも保存
            if self.driver:
                with open("error_page.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                logger.info("エラー時のページソースを保存しました: error_page.html")
            raise AuthenticationError(f"ログインプロセスでエラーが発生: {e}") from e
        except (GmailApiError, VerificationCodeError) as e:
            logger.error("2段階認証中にエラーが発生: %s", e)
            raise AuthenticationError(f"認証コードの取得に失敗: {e}") from e
        except Exception as e:
            logger.error("予期せぬエラーが発生: %s", e)
            # デバッグのためにエラー時のページソースも保存
            if self.driver:
                with open("error_page.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                logger.info("エラー時のページソースを保存しました: error_page.html")
            raise AuthenticationError(
                f"ログイン処理中に予期せぬエラーが発生: {e}"
            ) from e

    def _handle_two_factor_authentication(self, gmail_client: GmailClient) -> None:
        """二段階認証処理を行う。"""
        try:
            code_input = self.wait_and_find_element(By.NAME, "email_otp", timeout=3)  # type: ignore
        except ScrapingError:
            try:
                code_input = self.wait_and_find_element(
                    By.NAME, "mfid_user[otp_attempt]", timeout=3
                )  # type: ignore
            except ScrapingError:
                return
        logger.info("2段階認証が要求されました")
        time.sleep(5)
        verification_code = gmail_client.get_verification_code()
        logger.info("認証コードを取得しました: %s", verification_code)
        code_input.send_keys(verification_code)
        logger.info("認証コードを入力")
        code_input.submit()
        logger.info("認証コードの送信完了")

    def get_links_for_download(self, page_url: str) -> list[str]:
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

        logger.info("ページからダウンロードリンクの抽出を開始: %s", page_url)
        self.driver.get(page_url)

        try:
            # URLに基づいて処理を分岐
            if "/accounts" in page_url:
                self.wait_and_find_element(By.CSS_SELECTOR, ".btn.btn-warning").click()  # type: ignore
                logger.info("アカウントページ用の処理を実行します")
                return self._extract_links_from_accounts_page()
            if "/bs/history" in page_url:
                logger.info("履歴ページ用の処理を実行します")
                return self._extract_links_from_history_page()
            logger.warning("未知のページタイプです: %s", page_url)
            raise ScrapingError(f"未知のページタイプです: {page_url}")

        except Exception as e:
            raise ScrapingError(f"ダウンロードリンクの抽出に失敗しました: {e}") from e

    def _extract_links_from_accounts_page(self) -> list[str]:
        """アカウントページからリンクを抽出。

        Returns:
            List[str]: 抽出されたリンクのリスト。

        Raises:
            ScrapingError: リンクの抽出に失敗した場合。

        """
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
                        "アカウントリンクの抽出に失敗しました: %s"
                        "（現在の抽出済みリンク数: %d）",
                        e,
                        len(links),
                    )
                    continue

            logger.info(
                "アカウントページからのリンク抽出が完了しました。"
                "抽出されたリンク数: %d",
                len(links),
            )
            return links

        except Exception as e:
            logger.error("アカウントページからのリンク抽出に失敗しました: %s", e)
            raise ScrapingError(
                f"アカウントページからのリンク抽出に失敗しました: {e}"
            ) from e

    def _extract_links_from_history_page(self) -> list[str]:
        """履歴ページからリンクを抽出。

        Returns:
            List[str]: 抽出されたリンクのリスト。

        Raises:
            ScrapingError: リンクの抽出に失敗した場合。

        """
        if not self.driver:
            raise ScrapingError("WebDriverが初期化されていません。")
        return [self.driver.current_url]

    def get_cookies(self) -> list[dict]:
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
