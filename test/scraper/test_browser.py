"""BrowserManagerのテスト。"""

from unittest.mock import MagicMock, patch, mock_open

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

from exceptions.custom_exceptions import (
    AuthenticationError,
    GmailApiError,
    ScrapingError,
    VerificationCodeError,
)
from scraper.browser import BrowserManager
from scraper.gmail_client import GmailClient


@pytest.fixture
def browser_manager():
    """テスト用のBrowserManagerインスタンスを生成。"""
    return BrowserManager()


@pytest.fixture
def mock_gmail_client():
    """GmailClientのモックを提供するフィクスチャ。"""
    mock = MagicMock(spec=GmailClient)
    mock.get_latest_verification_email_id.return_value = "test_email_id"
    return mock


@pytest.fixture
def mock_form_elements():
    """フォーム要素のモックを提供するフィクスチャ。"""
    return {"email": MagicMock(), "password": MagicMock(), "code": MagicMock()}


@pytest.fixture
def mock_browser_setup(browser_manager, mock_gmail_client, mock_form_elements):
    """ブラウザのセットアップを提供するフィクスチャ。"""
    mock_driver = MagicMock()
    mock_driver.page_source = "mock page source"
    elements = mock_form_elements

    with patch(
        "scraper.browser.GmailClient", return_value=mock_gmail_client
    ), patch.object(browser_manager, "driver", mock_driver), patch(
        "builtins.open", mock_open()
    ) as mock_file:
        yield {
            "driver": mock_driver,
            "gmail": mock_gmail_client,
            "elements": elements,
            "mock_file": mock_file,
        }


@pytest.fixture
def mock_login_setup(mock_browser_setup):
    """ログインテスト用のセットアップ。"""
    mock_success_element = MagicMock()
    mock_browser_setup["success_element"] = mock_success_element
    return mock_browser_setup


def test_init(browser_manager):
    """初期化のテスト。"""
    assert browser_manager.driver is None
    assert browser_manager.timeout > 0
    assert browser_manager.retry_count > 0


def test_context_manager(browser_manager):
    """コンテキストマネージャーのテスト。"""
    with patch("selenium.webdriver.Chrome") as mock_chrome, patch(
        "selenium.webdriver.chrome.service.Service"
    ), patch("os.path.exists", return_value=True):
        mock_driver = MagicMock()
        mock_driver.page_source = "mock page source"
        mock_chrome.return_value = mock_driver

        with browser_manager as manager:
            assert manager.driver is not None
            assert isinstance(manager, BrowserManager)

        # __exit__でdriverがクリーンアップされることを確認
        assert browser_manager.driver is None
        mock_driver.quit.assert_called_once()


def test_setup_driver_success(browser_manager):
    """WebDriver設定の成功テスト。"""
    with patch("selenium.webdriver.Chrome") as mock_chrome, patch(
        "selenium.webdriver.chrome.service.Service"
    ), patch("os.path.exists", return_value=True):
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        browser_manager.setup_driver()
        assert browser_manager.driver is not None
        mock_chrome.assert_called_once()


def test_setup_driver_failure(browser_manager):
    """WebDriver設定の失敗テスト。"""
    with (
        patch("selenium.webdriver.Chrome") as mock_chrome,
        patch("selenium.webdriver.chrome.service.Service"),
        patch("os.path.exists", return_value=True),
    ):
        mock_chrome.side_effect = WebDriverException("接続エラー")

        with pytest.raises(ScrapingError) as exc_info:
            browser_manager.setup_driver()
        assert "WebDriverの初期化に失敗しました" in str(exc_info.value)


@pytest.mark.parametrize(
    "by,value",
    [
        (By.ID, "test-id"),
        (By.CLASS_NAME, "test-class"),
        (By.NAME, "test-name"),
        (By.CSS_SELECTOR, ".test-selector"),
    ],
)
def test_wait_and_find_element_success(browser_manager, by, value):
    """要素検索の成功テスト。"""
    mock_driver = MagicMock()
    mock_element = MagicMock()
    mock_driver.find_element.return_value = mock_element

    with patch.object(browser_manager, "driver", mock_driver):
        result = browser_manager.wait_and_find_element(by, value)
        assert result is not None


def test_wait_and_find_element_timeout(browser_manager):
    """要素検索のタイムアウトテスト。"""
    mock_driver = MagicMock()
    mock_driver.find_element.side_effect = TimeoutException("タイムアウト")

    with patch.object(browser_manager, "driver", mock_driver):
        with pytest.raises(ScrapingError) as exc_info:
            browser_manager.wait_and_find_element(By.ID, "test-id")
        assert "要素が見つかりませんでした" in str(exc_info.value)


def test_wait_and_find_element_invalid_by(browser_manager):
    """無効な検索方法のテスト。"""
    mock_driver = MagicMock()
    with patch.object(browser_manager, "driver", mock_driver):
        with pytest.raises(ScrapingError) as exc_info:
            browser_manager.wait_and_find_element("INVALID", "test")
        assert "無効な検索方法です" in str(exc_info.value)


def test_wait_and_find_element_without_driver(browser_manager):
    """WebDriver未初期化時のテスト。"""
    with pytest.raises(ScrapingError) as exc_info:
        browser_manager.wait_and_find_element(By.ID, "test-id")
    assert "WebDriverが初期化されていません" in str(exc_info.value)


def test_get_links_for_download_without_driver(browser_manager):
    """WebDriver未初期化時のget_links_for_downloadテスト。"""
    with pytest.raises(ScrapingError) as exc_info:
        browser_manager.get_links_for_download("http://example.com")
    assert "WebDriverが初期化されていません" in str(exc_info.value)


def test_get_links_for_download_with_element_error(browser_manager):
    """要素検索エラー時のget_links_for_downloadテスト。"""
    mock_driver = MagicMock()
    mock_accounts_table = MagicMock()
    mock_table = MagicMock()

    # find_elementsが例外を投げるように設定
    mock_table.find_elements.side_effect = NoSuchElementException(
        "要素が見つかりません"
    )
    mock_accounts_table.find_element.return_value = mock_table

    with patch.object(browser_manager, "driver", mock_driver), patch.object(
        browser_manager, "wait_and_find_element"
    ) as mock_find:
        mock_find.return_value = mock_accounts_table
        with pytest.raises(ScrapingError) as exc_info:
            # URLを/accountsに変更
            browser_manager.get_links_for_download("http://example.com/accounts")
        # 実装の例外メッセージに合わせて修正
        assert "テーブルの行データの抽出に失敗しました" in str(exc_info.value)


def test_get_cookies_without_driver(browser_manager):
    """WebDriver未初期化時のget_cookiesテスト。"""
    with pytest.raises(ScrapingError) as exc_info:
        browser_manager.get_cookies()
    assert "WebDriverが初期化されていません" in str(exc_info.value)


def test_retry_operation_with_multiple_exceptions(browser_manager):
    """複数の異なる例外が発生するリトライ処理のテスト。"""
    mock_operation = MagicMock()
    mock_operation.side_effect = [
        NoSuchElementException("要素が見つかりません"),
        StaleElementReferenceException("要素が古くなっています"),
        "success",
    ]

    result = browser_manager.retry_operation(mock_operation)
    assert result == "success"
    assert mock_operation.call_count == 3


def test_retry_operation_with_custom_args(browser_manager):
    """カスタム引数を使用したリトライ処理のテスト。"""
    mock_operation = MagicMock()
    mock_operation.side_effect = [NoSuchElementException, "success"]

    result = browser_manager.retry_operation(
        mock_operation, "test_arg", kwarg="test_kwarg"
    )
    assert result == "success"
    assert mock_operation.call_count == 2
    mock_operation.assert_called_with("test_arg", kwarg="test_kwarg")


def test_retry_operation_success(browser_manager):
    """リトライ操作の成功テスト。"""
    mock_operation = MagicMock()
    mock_operation.return_value = "success"

    result = browser_manager.retry_operation(mock_operation, "arg1", kwarg1="value1")
    assert result == "success"
    mock_operation.assert_called_once_with("arg1", kwarg1="value1")


def test_retry_operation_retry_and_succeed(browser_manager):
    """リトライ後に成功するテスト。"""
    mock_operation = MagicMock()
    mock_operation.side_effect = [NoSuchElementException, "success"]

    result = browser_manager.retry_operation(mock_operation)
    assert result == "success"
    assert mock_operation.call_count == 2


def test_retry_operation_all_failures(browser_manager):
    """全リトライ失敗のテスト。"""
    mock_operation = MagicMock()
    mock_operation.side_effect = StaleElementReferenceException

    with pytest.raises(ScrapingError) as exc_info:
        browser_manager.retry_operation(mock_operation)
    assert "操作が" in str(exc_info.value)
    assert mock_operation.call_count == browser_manager.retry_count


def test_login_success_with_2fa(
    browser_manager, mock_browser_setup, mock_form_elements
):
    """2段階認証を含むログイン成功のテスト。"""
    mock_setup = mock_browser_setup
    mock_setup["gmail"].get_latest_verification_email_id.side_effect = [
        "old_email_id",
        "new_email_id",
    ]
    mock_setup["gmail"].get_verification_code_by_id.return_value = "123456"

    mock_success_element = MagicMock()
    with patch.object(browser_manager, "wait_and_find_element") as mock_find:
        mock_find.side_effect = [
            mock_form_elements["email"],
            mock_form_elements["password"],
            mock_form_elements["code"],
            mock_success_element,
        ]

        browser_manager.login("test@example.com", "password123")

        # 各要素への操作を確認
        mock_form_elements["email"].send_keys.assert_called_with("test@example.com")
        mock_form_elements["email"].submit.assert_called_once()
        mock_form_elements["password"].send_keys.assert_called_with("password123")
        mock_form_elements["password"].submit.assert_called_once()
        mock_form_elements["code"].send_keys.assert_called_with("123456")
        mock_form_elements["code"].submit.assert_called_once()


def test_login_2fa_code_expired(
    browser_manager, mock_browser_setup, mock_form_elements
):
    """2段階認証コードの有効期限切れのテスト。"""
    mock_setup = mock_browser_setup
    mock_setup["gmail"].get_latest_verification_email_id.return_value = "test_email_id"
    mock_setup["gmail"].get_verification_code_by_id.side_effect = VerificationCodeError(
        "認証コードの有効期限が切れています"
    )

    with patch.object(browser_manager, "wait_and_find_element") as mock_find:
        mock_find.side_effect = [
            mock_form_elements["email"],
            mock_form_elements["password"],
            mock_form_elements["code"],
        ]

        with pytest.raises(AuthenticationError) as exc_info:
            browser_manager.login("test@example.com", "password123")
        assert "2段階認証に失敗しました" in str(exc_info.value)


def test_wait_for_new_verification_email_success(browser_manager, mock_gmail_client):
    """新しい認証メール待機の成功テスト。"""
    mock_gmail_client.get_latest_verification_email_id.side_effect = [
        "old_id",
        "new_id",
    ]

    result = browser_manager.wait_for_new_verification_email(
        mock_gmail_client, "old_id"
    )
    assert result == "new_id"
    assert mock_gmail_client.get_latest_verification_email_id.call_count == 2


def test_wait_for_new_verification_email_timeout(browser_manager, mock_gmail_client):
    """認証メール待機のタイムアウトテスト。"""
    with patch("time.sleep", return_value=None):
        mock_gmail_client.get_latest_verification_email_id.return_value = "old_id"

        with pytest.raises(VerificationCodeError) as exc_info:
            browser_manager.wait_for_new_verification_email(mock_gmail_client, "old_id")
        assert "新しい認証メールの到着待機がタイムアウトしました" in str(exc_info.value)


def test_wait_for_new_verification_email_api_error(browser_manager):
    with patch("time.sleep", return_value=None):
        """Gmail APIエラー時のテスト。"""
        mock_gmail_client = MagicMock(spec=GmailClient)
        mock_gmail_client.get_latest_verification_email_id.side_effect = GmailApiError(
            "API Error"
        )

        with pytest.raises(VerificationCodeError) as exc_info:
            browser_manager.wait_for_new_verification_email(mock_gmail_client)
        assert "新しい認証メールの到着待機がタイムアウトしました" in str(exc_info.value)


def test_login_failure(browser_manager, mock_browser_setup):
    """ログイン失敗のテスト。"""
    mock_setup = mock_browser_setup
    mock_setup["driver"].page_source = "mock page source"

    with patch.object(browser_manager, "wait_and_find_element") as mock_find, patch(
        "builtins.open", mock_open()
    ):
        mock_find.side_effect = TimeoutException("タイムアウト")

        with pytest.raises(AuthenticationError) as exc_info:
            browser_manager.login("test@example.com", "password123")
        assert "ログインフォームの要素が見つかりませんでした" in str(exc_info.value)


def test_get_links_for_download_success(browser_manager):
    """ダウンロードリンク取得の成功テスト。"""
    mock_driver = MagicMock()
    mock_table = MagicMock()
    mock_row = MagicMock()

    # モックの設定
    mock_cell = MagicMock()
    mock_link = MagicMock()
    mock_link.get_attribute.return_value = "http://example.com/download"

    # モックの連鎖を設定
    mock_cell.find_element.return_value = mock_link
    mock_row.find_element.return_value = mock_cell

    # 追加の設定: find_elementメソッドのモック
    mock_table.find_element.return_value = mock_table
    mock_table.find_elements.return_value = [
        MagicMock(),
        mock_row,
    ]  # ヘッダー行 + データ行

    with (
        patch.object(browser_manager, "driver", mock_driver),
        patch.object(browser_manager, "wait_and_find_element") as mock_find,
    ):
        mock_find.side_effect = [mock_table]

        # URLを/accountsに変更
        links = browser_manager.get_links_for_download("http://example.com/accounts")
        assert len(links) == 1
        assert links[0] == "http://example.com/download"

        # メソッドが正しく呼び出されたことを確認
        mock_row.find_element.assert_called_with(By.TAG_NAME, "td")
        mock_cell.find_element.assert_called_with(By.TAG_NAME, "a")
        mock_link.get_attribute.assert_called_with("href")


def test_get_links_for_download_no_links(browser_manager):
    """リンクが見つからない場合のテスト。"""
    mock_driver = MagicMock()
    mock_table = MagicMock()
    mock_table.find_elements.return_value = []

    with (
        patch.object(browser_manager, "driver", mock_driver),
        patch.object(browser_manager, "wait_and_find_element") as mock_find,
    ):
        mock_find.return_value = mock_table

        # URLを/accountsに変更
        links = browser_manager.get_links_for_download("http://example.com/accounts")
        assert len(links) == 0


def test_get_links_for_download_failure(browser_manager):
    """リンク取得の失敗テスト。"""
    mock_driver = MagicMock()
    with (
        patch.object(browser_manager, "driver", mock_driver),
        patch.object(browser_manager, "wait_and_find_element") as mock_find,
    ):
        mock_find.side_effect = ScrapingError("要素が見つかりません")

        with pytest.raises(ScrapingError) as exc_info:
            browser_manager.get_links_for_download("http://example.com/accounts")
        assert "ダウンロードリンクの抽出に失敗しました" in str(exc_info.value)


def test_get_cookies_success(browser_manager):
    """クッキー取得の成功テスト。"""
    mock_driver = MagicMock()
    mock_cookies = [{"name": "test", "value": "value"}]
    mock_driver.get_cookies.return_value = mock_cookies

    with patch.object(browser_manager, "driver", mock_driver):
        cookies = browser_manager.get_cookies()
        assert cookies == mock_cookies


def test_get_cookies_failure(browser_manager):
    """クッキー取得の失敗テスト。"""
    mock_driver = MagicMock()
    mock_driver.get_cookies.side_effect = WebDriverException("クッキー取得エラー")

    with patch.object(browser_manager, "driver", mock_driver):
        with pytest.raises(ScrapingError) as exc_info:
            browser_manager.get_cookies()
        assert "クッキーの取得に失敗しました" in str(exc_info.value)
