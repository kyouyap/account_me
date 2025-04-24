"""認証関連クラスのテスト。"""

from unittest.mock import MagicMock, patch
import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from scraper.auth.authenticator import (
    AuthenticationManager,
    MoneyForwardTwoFactorAuthenticator,
)
from scraper.base.selenium_manager import BaseSeleniumManager
from scraper.gmail_client import GmailClient
from exceptions.custom_exceptions import (
    AuthenticationError,
    GmailApiError,
    VerificationCodeError,
)


# フィクスチャ
@pytest.fixture
def mock_browser():
    """BaseSeleniumManagerのモックを提供。"""
    browser = MagicMock(spec=BaseSeleniumManager)
    browser.driver = MagicMock(spec=WebDriver)
    return browser


@pytest.fixture
def mock_gmail_client():
    """GmailClientのモックを提供。"""
    return MagicMock(spec=GmailClient)


@pytest.fixture
def mock_element():
    """WebElementのモックを提供。"""
    return MagicMock(spec=WebElement)


@pytest.fixture
def two_factor_auth(mock_browser, mock_gmail_client):
    """MoneyForwardTwoFactorAuthenticatorのインスタンスを提供。"""
    return MoneyForwardTwoFactorAuthenticator(mock_browser, mock_gmail_client)


@pytest.fixture
def auth_manager(mock_browser):
    """AuthenticationManagerのインスタンスを提供。"""
    return AuthenticationManager(mock_browser)


# TwoFactorAuthenticatorのテスト
def test_2fa_not_required(two_factor_auth, mock_browser):
    """2段階認証が要求されない場合のテスト。"""
    mock_browser.wait_and_find_element.side_effect = TimeoutException()
    two_factor_auth.handle_2fa("test@example.com")
    # TimeoutExceptionが発生しても正常に処理されることを確認


def test_2fa_success(two_factor_auth, mock_browser, mock_gmail_client, mock_element):
    """2段階認証が成功する場合のテスト。"""
    mock_browser.wait_and_find_element.return_value = mock_element
    mock_gmail_client.get_latest_verification_email_id.return_value = "email_id_1"
    mock_gmail_client.get_verification_code_by_id.return_value = "123456"

    two_factor_auth.handle_2fa("test@example.com")

    mock_element.send_keys.assert_called_once_with("123456")
    mock_element.submit.assert_called_once()


def test_2fa_gmail_api_error(
    two_factor_auth, mock_browser, mock_gmail_client, mock_element
):
    """GmailAPI関連のエラーが発生した場合のテスト。"""
    mock_browser.wait_and_find_element.return_value = mock_element
    mock_gmail_client.get_latest_verification_email_id.side_effect = GmailApiError(
        "API Error"
    )

    with pytest.raises(AuthenticationError, match="2段階認証に失敗しました"):
        two_factor_auth.handle_2fa("test@example.com")


def test_2fa_verification_timeout(
    two_factor_auth, mock_browser, mock_gmail_client, mock_element
):
    """認証コードの取得がタイムアウトした場合のテスト。"""
    mock_browser.wait_and_find_element.return_value = mock_element
    mock_gmail_client.get_latest_verification_email_id.return_value = "same_id"

    with pytest.raises(AuthenticationError, match="2段階認証に失敗しました"):
        two_factor_auth.handle_2fa("test@example.com")


# AuthenticationManagerのテスト
def test_login_success(auth_manager, mock_browser, mock_element):
    """ログインが成功する場合のテスト。"""
    mock_browser.wait_and_find_element.return_value = mock_element

    auth_manager.login("test@example.com", "password")

    # メールアドレスとパスワードが正しく入力されたことを確認
    mock_element.send_keys.assert_any_call("test@example.com")
    mock_element.send_keys.assert_any_call("password")
    mock_element.submit.assert_called()

    # ログイン成功の確認が行われたことを確認
    mock_browser.wait_and_find_element.assert_any_call(By.CLASS_NAME, "accounts")


def test_login_browser_not_initialized(auth_manager, mock_browser):
    """ブラウザが初期化されていない場合のテスト。"""
    mock_browser.driver = None

    with pytest.raises(AuthenticationError, match="ブラウザが初期化されていません"):
        auth_manager.login("test@example.com", "password")


def test_login_element_not_found(auth_manager, mock_browser):
    """要素が見つからない場合のテスト。"""
    mock_browser.wait_and_find_element.side_effect = TimeoutException()

    with pytest.raises(
        AuthenticationError, match="ログインフォームの要素が見つかりませんでした"
    ):
        auth_manager.login("test@example.com", "password")


def test_login_with_2fa(mock_browser, mock_element):
    """2段階認証付きのログインテスト。"""
    mock_two_factor_auth = MagicMock()
    auth_manager = AuthenticationManager(mock_browser, mock_two_factor_auth)
    mock_browser.wait_and_find_element.return_value = mock_element

    auth_manager.login("test@example.com", "password")

    # 2段階認証が呼び出されたことを確認
    mock_two_factor_auth.handle_2fa.assert_called_once_with("test@example.com")


def test_login_unexpected_error(auth_manager, mock_browser):
    """予期せぬエラーが発生した場合のテスト。"""
    mock_browser.driver.get.side_effect = Exception("Unexpected error")

    with pytest.raises(AuthenticationError, match="予期せぬエラーが発生"):
        auth_manager.login("test@example.com", "password")
