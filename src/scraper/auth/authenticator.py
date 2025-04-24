"""認証関連クラスモジュール。"""

import logging
from typing import Protocol, Optional
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from scraper.base.selenium_manager import BaseSeleniumManager
from scraper.gmail_client import GmailClient
from config.settings import settings
from exceptions.custom_exceptions import (
    AuthenticationError,
    GmailApiError,
    VerificationCodeError,
)

logger = logging.getLogger(__name__)


class TwoFactorAuthenticator(Protocol):
    """2段階認証の処理を行うインターフェース。"""

    def handle_2fa(self, email: str) -> None:
        """2段階認証を処理する。

        Args:
            email: 認証コードが送信されるメールアドレス。

        Raises:
            AuthenticationError: 2段階認証に失敗した場合。
        """
        ...


class MoneyForwardTwoFactorAuthenticator:
    """MoneyForward用の2段階認証処理クラス。"""

    def __init__(self, browser: BaseSeleniumManager, gmail_client: GmailClient) -> None:
        """初期化。

        Args:
            browser: ブラウザ操作用のインスタンス。
            gmail_client: Gmail APIクライアント。
        """
        self._browser = browser
        self._gmail_client = gmail_client

    def handle_2fa(self, email: str) -> None:
        """2段階認証を処理する。

        Args:
            email: 認証コードが送信されるメールアドレス。

        Raises:
            AuthenticationError: 2段階認証に失敗した場合。
        """
        try:
            # 現在の最新メールIDを取得
            logger.info("現在の最新メールIDを取得")
            last_email_id = self._gmail_client.get_latest_verification_email_id()

            # 2段階認証の確認
            logger.info("2段階認証フォームの有無を確認")
            try:
                code_input = self._browser.wait_and_find_element(
                    By.NAME, "email_otp", timeout=3
                )
                logger.info("2段階認証が要求されました")
            except TimeoutException:
                try:
                    # 古い形式の2段階認証フォームを試行
                    code_input = self._browser.wait_and_find_element(
                        By.NAME, "mfid_user[otp_attempt]", timeout=3
                    )
                    logger.info("古い形式の2段階認証フォームが見つかりました")
                except TimeoutException:
                    logger.info("2段階認証は要求されませんでした")
                    return

            # 送信後の新しいメールを待機
            logger.info("新しい認証メールの到着を待機")
            new_email_id = self._wait_for_new_verification_email(last_email_id)

            # 新しいメールから認証コードを取得
            logger.info("新しいメールから認証コードを取得")
            verification_code = self._gmail_client.get_verification_code_by_id(
                new_email_id
            )
            logger.info("認証コードを取得しました: %s", verification_code)

            # 認証コードを入力して送信
            logger.info("認証コードを入力: %s", verification_code)
            code_input.send_keys(verification_code)
            logger.info("認証コードフォームを送信")
            code_input.submit()
            logger.info("認証コードの送信完了")

        except (GmailApiError, VerificationCodeError) as e:
            logger.error("2段階認証中にエラーが発生: %s", e)
            raise AuthenticationError(f"2段階認証に失敗しました: {e}") from e
        except Exception as e:
            logger.error("2段階認証中に予期せぬエラーが発生: %s", e)
            raise AuthenticationError(f"2段階認証中に予期せぬエラーが発生: {e}") from e

    def _wait_for_new_verification_email(
        self, last_email_id: Optional[str] = None
    ) -> str:
        """指定されたGmailアカウントに新しい認証メールが到着するのを待機。

        Args:
            last_email_id: 前回取得したメールのID。

        Returns:
            str: 新しく到着した認証メールのID。

        Raises:
            VerificationCodeError: 新しい認証メールの取得に失敗した場合。
        """
        max_attempts = 10  # 最大待機回数
        for attempt in range(max_attempts):
            try:
                # 新しいメールを検索
                email_id = self._gmail_client.get_latest_verification_email_id()

                # 新しいメールが来ているか確認
                if last_email_id is None or email_id != last_email_id:
                    logger.info("新しい認証メールを検出: %s", email_id)
                    return email_id

                logger.info(
                    "メールの到着を待機中... 試行回数: %d/%d", attempt + 1, max_attempts
                )
                import time

                time.sleep(3)  # 3秒待機

            except Exception as e:
                logger.warning("メール検索中にエラー: %s", e)
                time.sleep(3)

        raise VerificationCodeError("新しい認証メールの到着待機がタイムアウトしました")


class AuthenticationManager:
    """認証処理を管理するクラス。"""

    def __init__(
        self,
        browser: BaseSeleniumManager,
        two_factor_auth: Optional[TwoFactorAuthenticator] = None,
    ) -> None:
        """初期化。

        Args:
            browser: ブラウザ操作用のインスタンス。
            two_factor_auth: 2段階認証処理用のインスタンス。
        """
        self._browser = browser
        self._two_factor_auth = two_factor_auth

    def login(self, email: str, password: str) -> None:
        """MoneyForwardにログイン。

        Args:
            email: ログイン用メールアドレス。
            password: ログイン用パスワード。

        Raises:
            AuthenticationError: ログインに失敗した場合。
        """
        if not self._browser.driver:
            raise AuthenticationError("ブラウザが初期化されていません。")

        url = f"{settings.moneyforward.base_url}{settings.moneyforward.endpoints.login}"
        try:
            self._browser.driver.get(url)
            logger.info("MoneyForwardログインページにアクセスしています: %s", url)

            # メールアドレス入力
            logger.info("メールアドレス入力フォームを探索中")
            email_input = self._browser.wait_and_find_element(
                By.NAME, "mfid_user[email]"
            )
            logger.info("メールアドレスを入力: %s", email)
            email_input.send_keys(email)
            logger.info("メールアドレスフォームを送信")
            email_input.submit()
            logger.info("メールアドレス送信完了")

            # パスワード入力
            logger.info("パスワード入力フォームを探索中")
            password_input = self._browser.wait_and_find_element(
                By.NAME, "mfid_user[password]"
            )
            logger.debug("パスワードを入力")
            password_input.send_keys(password)
            logger.info("パスワードフォームを送信")
            password_input.submit()
            logger.info("パスワード送信完了")

            # 2段階認証の処理
            if self._two_factor_auth:
                self._two_factor_auth.handle_2fa(email)

            # ログイン成功の確認
            logger.info("ログイン成功の確認を開始")
            self._browser.wait_and_find_element(By.CLASS_NAME, "accounts")
            logger.info("MoneyForwardへのログインが完了しました。ユーザー: %s", email)

        except TimeoutException as e:
            logger.error("要素待機中にタイムアウトが発生: %s", e)
            # デバッグのためにエラー時のページソースも保存
            if self._browser.driver:
                with open("error_page.html", "w", encoding="utf-8") as f:
                    f.write(self._browser.driver.page_source)
                logger.info("エラー時のページソースを保存しました: error_page.html")
            raise AuthenticationError(
                "ログインフォームの要素が見つかりませんでした。"
            ) from e
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error("ログイン処理中に予期せぬエラーが発生: %s", e)
            # デバッグのためにエラー時のページソースも保存
            if self._browser.driver:
                with open("error_page.html", "w", encoding="utf-8") as f:
                    f.write(self._browser.driver.page_source)
                logger.info("エラー時のページソースを保存しました: error_page.html")
            raise AuthenticationError(
                f"ログイン処理中に予期せぬエラーが発生: {e}"
            ) from e
